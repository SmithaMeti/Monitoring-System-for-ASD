import os
import cv2
import base64
import numpy as np
import tensorflow as tf
from mtcnn import MTCNN
from keras_facenet import FaceNet
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import shutil

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")


CORS(app, supports_credentials=True)


DB_URL = os.environ.get("DATABASE_URL", "sqlite:///users.sqlite3")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


MODEL_FILENAME = "autism_mobilenetv2.h5"
USERS_DIR = "users"
IMG_W, IMG_H = 224, 224
FACE_MATCH_THRESHOLD = 0.55    
ASD_THRESHOLD = 0.50     
CAPTURE_DELAY = timedelta(seconds=3) 
USE_LAST_IMAGE_FOR_FINAL = False
os.makedirs(USERS_DIR, exist_ok=True)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    plan_count = db.Column(db.Integer, nullable=True)
    last_capture_ts = db.Column(db.DateTime, nullable=True)
    final_label = db.Column(db.String(32), nullable=True)
    final_prob = db.Column(db.Float, nullable=True)
    captures = db.relationship("Capture", backref="user", lazy=True, cascade="all, delete-orphan")

class Capture(db.Model):
    __tablename__ = "captures"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    ts = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    prob = db.Column(db.Float, nullable=True)
    label = db.Column(db.String(32), nullable=True)

with app.app_context():
    db.create_all()


print("Loading ML models (face detector, embedder, ASD model)...")
try:

    model = tf.keras.models.load_model(MODEL_FILENAME) if os.path.exists(MODEL_FILENAME) else None
    detector = MTCNN()
    embedder = FaceNet()
    print("Models loaded (or available).")
except Exception as e:
    print("Error loading models:", e)
    detector = None
    embedder = None
    model = None

# ---------------- Helpers ----------------
def _user_folder(username):
    return os.path.join(USERS_DIR, username)

def _now():
    return datetime.utcnow()

def get_embedding(face_pixels):
    # face_pixels expected as RGB numpy array
    face_pixels = cv2.resize(face_pixels, (160, 160))
    face_pixels = face_pixels.astype('float32')
    emb = embedder.embeddings([face_pixels])
    return emb  # shape (1,512) typically

def predict_asd(face_img):
    # If model isn't loaded, return placeholder
    if model is None:
        return "Non-Autistic", 0.0
    img_array = np.expand_dims(face_img.astype("float32") / 255.0, axis=0)
    prob = float(model.predict(img_array, verbose=0)[0][0])
    cls = "Autistic" if prob > ASD_THRESHOLD else "Non-Autistic"
    return cls, prob

def decode_and_find_face(base64_image_string):
    try:
        header, encoded = base64_image_string.split(",", 1)
    except Exception:
        encoded = base64_image_string
    try:
        image_data = base64.b64decode(encoded)
    except Exception:
        return None, None
    np_arr = np.frombuffer(image_data, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return None, None
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    faces = detector.detect_faces(img_rgb) if detector else []
    if not faces:
        return None, None
    # pick largest face
    face_data = max(faces, key=lambda x: x['box'][2] * x['box'][3])
    x, y, w, h = face_data['box']
    x, y = max(0, x), max(0, y)
    face_crop = img_rgb[y:y+h, x:x+w]
    if face_crop.size == 0:
        return None, None
    return img_rgb, face_crop

def build_user_gallery(user):
    captures = Capture.query.filter_by(user_id=user.id).order_by(Capture.ts).all()
    gallery = []
    for c in captures:
        gallery.append({
            "image_url": f"/users/{user.username}/{c.filename}",
            "label": c.label,
            "probability": c.prob,
            "timestamp": c.ts.isoformat()
        })
    return gallery

def aggregate_final_result(user):
    captures = Capture.query.filter_by(user_id=user.id).all()
    probs = [c.prob for c in captures if c.prob is not None]
    if not probs:
        return None
    mean_prob = float(np.mean(probs))
    label = "Autistic" if mean_prob > ASD_THRESHOLD else "Non-Autistic"
    return {"label": label, "prob": mean_prob}

# ---------------- Routes ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/users/<path:filename>")
def serve_user_image(filename):
    return send_from_directory(USERS_DIR, filename)

# ---- Auth ----
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required."}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"ok": False, "error": "Username already exists."}), 400
    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    os.makedirs(_user_folder(username), exist_ok=True)
    session["username"] = username
    return jsonify({"ok": True, "username": username})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"ok": False, "error": "Invalid credentials."}), 401
    session["username"] = username
    return jsonify({"ok": True, "username": username})

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/me", methods=["GET"])
def me():
    if "username" not in session:
        return jsonify({"ok": True, "logged_in": False})
    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        session.clear()
        return jsonify({"ok": True, "logged_in": False})
    remaining = None
    if user.last_capture_ts:
        delta = _now() - user.last_capture_ts
        remaining = max(0, int((CAPTURE_DELAY - delta).total_seconds()))
    progress = Capture.query.filter_by(user_id=user.id).count()
    final_result = None
    if user.final_label is not None and user.final_prob is not None:
        final_result = {"label": user.final_label, "prob": user.final_prob}
    gallery = build_user_gallery(user)
    return jsonify({
        "ok": True,
        "logged_in": True,
        "username": user.username,
        "plan_count": user.plan_count,
        "progress": progress,
        "remaining_seconds": remaining,
        "final_result": final_result,
        "gallery": gallery
    })

@app.route("/set_photo_plan", methods=["POST"])
def set_photo_plan():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json() or {}
    plan_count = data.get("planCount")
    if not isinstance(plan_count, int) or not (1 <= plan_count <= 10):
        return jsonify({"ok": False, "error": "Plan must be an integer 1–10."}), 400
    user = User.query.filter_by(username=session["username"]).first()
    user.plan_count = plan_count
    user.last_capture_ts = None
    user.final_label = None
    user.final_prob = None
    # remove old captures & files (optional) - keep minimal here
    db.session.commit()
    return jsonify({"ok": True, "plan_count": plan_count})

# ---- Capture endpoint (same-person enforcement) ----
@app.route("/capture", methods=["POST"])
def capture():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json() or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"ok": False, "error": "No image provided."}), 400

    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return jsonify({"ok": False, "error": "User not found."}), 404

    if not user.plan_count:
        return jsonify({"ok": False, "error": "Set your photo plan first."}), 400
    if user.final_label is not None:
        return jsonify({"ok": False, "error": "Plan already completed."}), 400

    # Enforce delay between captures
    if user.last_capture_ts:
        diff = _now() - user.last_capture_ts
        if diff < CAPTURE_DELAY:
            remaining = int((CAPTURE_DELAY - diff).total_seconds())
            return jsonify({"ok": False, "error": "Capture locked", "remaining_seconds": remaining}), 403

    # Face detection
    _, face_crop = decode_and_find_face(image_b64)
    if face_crop is None:
        return jsonify({"ok": False, "error": "No face detected."}), 400

    # create user folder
    folder = _user_folder(user.username)
    os.makedirs(folder, exist_ok=True)

    # load previous embedding if exists
    emb_path = os.path.join(folder, "embedding.npy")
    new_emb = get_embedding(face_crop) if embedder else None

    if os.path.exists(emb_path) and new_emb is not None:
        try:
            stored_emb = np.load(emb_path)
            sim = float(cosine_similarity(stored_emb, new_emb)[0][0])
        except Exception:
            sim = 0.0
        # If similarity is below threshold, reject capture as "Not same person"
        if sim < FACE_MATCH_THRESHOLD:
            return jsonify({"ok": False, "error": "Not same person", "similarity": sim}), 403
    else:
        # first-ever capture for this user: save embedding as the reference
        try:
            if new_emb is not None:
                np.save(emb_path, new_emb)
            sim = None
        except Exception:
            pass

    # Save image (resized) and perform ASD prediction
    face_resized = cv2.resize(face_crop, (IMG_W, IMG_H))
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    save_path = os.path.join(folder, filename)
    cv2.imwrite(save_path, cv2.cvtColor(face_resized, cv2.COLOR_RGB2BGR))

    # Do ASD prediction on resized image
    pred_label, pred_prob = predict_asd(face_resized)

    # Save capture record (store prob + label)
    cap = Capture(user_id=user.id, filename=filename, ts=_now(), prob=float(pred_prob), label=pred_label)
    user.last_capture_ts = _now()
    db.session.add(cap)

    # If done update final result
    db.session.commit()
    progress = Capture.query.filter_by(user_id=user.id).count()
    done = progress >= user.plan_count

    final_result = None
    final_gallery = None
    if done:
        if USE_LAST_IMAGE_FOR_FINAL:
            user.final_label = pred_label
            user.final_prob = float(pred_prob)
            final_result = {"label": pred_label, "prob": float(pred_prob)}
        else:
            agg = aggregate_final_result(user)
            if agg:
                user.final_label = agg["label"]
                user.final_prob = agg["prob"]
                final_result = agg
        db.session.commit()
        final_gallery = build_user_gallery(user)

    response = {
        "ok": True,
        "progress": progress,
        "plan_count": user.plan_count,
        "done": done,
        "image_url": f"/users/{user.username}/{filename}",
        "prediction": {"class": pred_label, "probability": float(pred_prob)},
        "final_result": final_result,
        "gallery": final_gallery
    }
    if 'sim' in locals() and sim is not None:
        response["similarity"] = sim
    return jsonify(response)

@app.route("/restart_plan", methods=["POST"])
def restart_plan():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return jsonify({"ok": False, "error": "User not found."}), 404
    # delete captures and files
    Capture.query.filter_by(user_id=user.id).delete()
    folder = _user_folder(user.username)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    user.plan_count = None
    user.last_capture_ts = None
    user.final_label = None
    user.final_prob = None
    db.session.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
