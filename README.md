# Monitoring System for ASD

A Flask-based web application for monitoring and detecting Autism Spectrum Disorder (ASD) using facial images. The system allows users to create a photo plan, capture images at set intervals, and uses deep learning models to predict the likelihood of ASD. It also ensures the same person is being captured throughout the session using facial recognition.

## Features

- **User Authentication:** Secure registration and login using secure password hashing.
- **Photo Plan:** Users can set a customized plan of 1 to 10 photos to be taken for analysis.
- **Face Detection & Verification:** Uses **MTCNN** for face detection and **FaceNet** to extract facial embeddings. This ensures that the same individual's face is captured consistently across the entire photo plan.
- **ASD Prediction:** Utilizes a trained **MobileNetV2** model (`autism_mobilenetv2.h5`) to analyze facial features and predict the probability of ASD.
- **Anti-Spam Delay:** Enforces a configurable delay (e.g., 3 seconds) between image captures to ensure proper intervals.
- **Result Aggregation:** Computes the mean probability across all captures in a plan to provide a final aggregated result (Autistic / Non-Autistic).
- **User Dashboard:** A gallery interface to view past captures, individual predictions, and the final aggregated result.

## Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-CORS
- **Database:** SQLite (Default, configurable via `DATABASE_URL` environment variable)
- **Machine Learning & Computer Vision:**
  - TensorFlow / Keras (MobileNetV2 for ASD classification)
  - OpenCV (`cv2`) for image processing
  - MTCNN for robust face detection
  - Keras-FaceNet for facial embeddings and cosine similarity matching
- **Frontend:** HTML, CSS, JavaScript (served via Flask templates and static files)

## Project Structure

```text
monitoring-system-ASD/
├── app.py                     # Main Flask application and API routes
├── autism_mobilenetv2.h5      # Pre-trained MobileNetV2 model for ASD prediction
├── requirements.txt           # Python dependencies (make sure to install Flask, TensorFlow, OpenCV, etc.)
├── static/                    # Static assets (CSS, JS, images)
├── templates/                 # HTML templates for the frontend
├── users/                     # Directory where user-captured images and embeddings are stored
└── instance/                  # Directory containing the SQLite database
```

## Setup and Installation

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd "folder name"
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   Make sure you have all required packages installed. You may need to ensure `flask`, `tensorflow`, `opencv-python`, `mtcnn`, `keras-facenet`, and `scikit-learn` are available.
   ```bash
   pip install -r requirements.txt
   pip install flask flask_sqlalchemy flask_cors werkzeug mtcnn keras-facenet
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```
   The application will be accessible at `http://localhost:5000` (or `http://0.0.0.0:5000` depending on your environment).

## How to Use

1. **Register/Login:** Create a new account or log into an existing one.
2. **Set Photo Plan:** Choose how many photos (1-10) you want to capture for the analysis.
3. **Capture Images:** Use your webcam/camera through the user interface to take photos. The system will verify if the face matches the first captured image.
4. **View Results:** After completing the required number of photos, the system will calculate and display your final aggregated result based on all captures.

## Environment Variables

- `FLASK_SECRET_KEY`: Set this to a secure random string for production to secure sessions.
- `DATABASE_URL`: Set this to use a different database (defaults to `sqlite:///users.sqlite3`).

## Notes

- The system relies on the pre-trained `autism_mobilenetv2.h5` model file. Ensure this file is present in the root directory before running the application.
- The default face matching threshold is set to `0.55`, and the ASD probability threshold is `0.50`. These can be adjusted in `app.py`.
