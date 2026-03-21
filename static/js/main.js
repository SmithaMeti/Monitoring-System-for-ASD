document.addEventListener('DOMContentLoaded', () => {
  const authView = document.getElementById('auth-view');
  const setupView = document.getElementById('setup-view');
  const mainView  = document.getElementById('main-view');

  const authUser = document.getElementById('auth-username');
  const authPass = document.getElementById('auth-password');
  const loginBtn = document.getElementById('login-btn');
  const registerBtn = document.getElementById('register-btn');
  const authError = document.getElementById('auth-error');

  const photoPlanInput = document.getElementById('photo-plan-input');
  const savePlanBtn = document.getElementById('save-plan-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const setupError = document.getElementById('setup-error');

  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const captureBtn = document.getElementById('capture-btn');
  const logoutBtn2 = document.getElementById('logout-btn-2');

  const restartBtnSetup = document.getElementById('restart-btn-setup');
  const restartBtnMain  = document.getElementById('restart-btn-main');

  const mainError = document.getElementById('main-error');
  const loader = document.getElementById('loader');
  const todayThumb = document.getElementById('today-thumb');
  const progressEl = document.getElementById('progress');
  const countdownEl = document.getElementById('countdown');
  const finalBox = document.getElementById('final-result');
  const finalText = document.getElementById('final-text');
  const mainInstructions = document.getElementById('main-instructions');

  const finalGallery = document.getElementById('final-gallery');
  const trendCanvas = document.getElementById('trend-chart');
  let trendChart = null;


  let me = null;
  let stream = null;
  let countdownTimer = null;


  function show(el) { if(el) el.style.display = 'block'; }
  function hide(el) { if(el) el.style.display = 'none'; }
  function setText(el, txt) { if(el) el.textContent = txt; }
  function fmtTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}h ${m}m ${s}s`;
  }
  function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setText(mainError, "Your browser does not support camera access.");
      show(mainError);
      return;
    }
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(s => {
        stream = s;
        video.srcObject = s;
        return video.play();
      })
      .catch(err => {
        console.error(err);
        setText(mainError, "Could not access the camera.");
        show(mainError);
      });
  }
  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    video.srcObject = null;
  }
  function renderProgress() {
    if (!me) return;
    const total = me.plan_count ?? 0;
    const have = me.progress ?? 0;
    if (total) {
      setText(progressEl, `Progress: ${have} / ${total} photo(s)`);
    } else {
      setText(progressEl, "");
    }
  }
  function renderCountdown() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
    if (!me || me.remaining_seconds === null || me.remaining_seconds === undefined) {
      setText(countdownEl, "");
      captureBtn.disabled = false;
      return;
    }
    let left = me.remaining_seconds;
    if (me.final_result) {
      setText(countdownEl, "");
      captureBtn.disabled = true;
      captureBtn.style.display = 'none';
      return;
    }
    if (left <= 0) {
      setText(countdownEl, "You can capture your next photo now.");
      captureBtn.disabled = false;
      return;
    }
    captureBtn.disabled = true;
    setText(countdownEl, `Next capture in ${fmtTime(left)}.`);
    countdownTimer = setInterval(() => {
      left -= 1;
      if (left <= 0) {
        clearInterval(countdownTimer);
        setText(countdownEl, "You can capture your next photo now.");
        captureBtn.disabled = false;
      } else {
        setText(countdownEl, `Next capture in ${fmtTime(left)}.`);
      }
    }, 1000);
  }
  function renderFinal() {
    if (me && me.final_result) {
      const label = me.final_result.label;
      const probPct = (me.final_result.prob * 100).toFixed(2);
      finalText.textContent = `${label}`;
      finalText.style.color = label === 'Autistic' ? '#d9534f' : '#5cb85c';
      show(finalBox);
      captureBtn.disabled = true;
      captureBtn.style.display = 'none';


      buildFinalGallery();
      renderTrendChart();
    } else {
      hide(finalBox);
      captureBtn.style.display = 'inline-block';
    }
  }
  function go(view) {
    hide(authView); hide(setupView); hide(mainView);
    if (view === 'auth') show(authView);
    if (view === 'setup') show(setupView);
    if (view === 'main') { show(mainView); startCamera(); }
    if (view !== 'main') stopCamera();
  }
  function clearErrors() {
    hide(authError); hide(setupError); hide(mainError);
  }


  async function api(path, method = 'GET', body = null) {
    const res = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: body ? JSON.stringify(body) : null
    });

    const text = await res.text();
    try { return JSON.parse(text); } catch (e) { return { ok: false, error: 'Invalid server response', raw: text }; }
  }


  function buildFinalGallery() {
  if (!finalGallery) return;
  finalGallery.innerHTML = '';
  if (!me || !me.gallery || !me.gallery.length) return;

  const finalIndex = me.gallery.length - 1;

  me.gallery.forEach((g, idx) => {
    const card = document.createElement('div');
    card.className = 'result-card';
    if (idx === finalIndex) card.classList.add('final-chosen');

    const img = document.createElement('img');
    img.src = `${g.image_url}?t=${Date.now()}`;
    img.alt = `Capture ${idx + 1}`;

    const p = document.createElement('p');
    p.textContent = g.label ? g.label : '';

    card.appendChild(img);
    card.appendChild(p);
    finalGallery.appendChild(card);
  });
}


  function renderTrendChart() {
    if (!trendCanvas) return;

    if (!me || !me.gallery || !me.gallery.length) {
      if (trendChart) { trendChart.destroy(); trendChart = null; }
      return;
    }

    const labels = me.gallery.map((g, i) => {
      if (g.timestamp) {
        try { return new Date(g.timestamp).toLocaleString(); } catch (e) {}
      }
      return `#${i+1}`;
    });

    const data = me.gallery.map(g => (typeof g.probability === 'number' ? +(g.probability * 100).toFixed(3) : null));
    const hasNumbers = data.some(v => typeof v === 'number' && !isNaN(v));
    if (!hasNumbers) {
      if (trendChart) { trendChart.destroy(); trendChart = null; }
      return;
    }

    if (trendChart) trendChart.destroy();

    trendChart = new Chart(trendCanvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'ASD Probability (%)',
          data,
          fill: false,
          tension: 0.25,
          pointRadius: 5
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: { beginAtZero: true, max: 100 },
          x: { ticks: { autoSkip: true, maxTicksLimit: 8 } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  async function refreshMe() {
    me = await api('/me');
    if (!me.ok || !me.logged_in) {
      go('auth');
      return;
    }
    if (!me.plan_count) {
      go('setup');
    } else {
      go('main');
      renderProgress();
      renderFinal();
      renderCountdown();
      mainInstructions.textContent = "Capture one photo each allowed interval until you finish your plan.";
      if (!me.final_result) {
        captureBtn.style.display = 'inline-block';
      }
    }
  }


  async function restartPlan() {
    hide(mainError);
    const res = await api('/restart_plan', 'POST');
    if (!res.ok) {
      setText(mainError, res.error || 'Failed to restart.');
      show(mainError);
      return;
    }
    todayThumb.innerHTML = '';
    await refreshMe();
  }


  loginBtn.addEventListener('click', async () => {
    clearErrors();
    const r = await api('/login', 'POST', { username: authUser.value, password: authPass.value });
    if (!r.ok) {
      authError.textContent = `Error: ${r.error}`;
      show(authError);
      return;
    }
    await refreshMe();
  });

  registerBtn.addEventListener('click', async () => {
    clearErrors();
    const r = await api('/register', 'POST', { username: authUser.value, password: authPass.value });
    if (!r.ok) {
      authError.textContent = `Error: ${r.error}`;
      show(authError);
      return;
    }
    await refreshMe();
  });

  logoutBtn.addEventListener('click', async () => {
    await api('/logout', 'POST');
    go('auth');
  });
  logoutBtn2.addEventListener('click', async () => {
    await api('/logout', 'POST');
    go('auth');
  });

  restartBtnSetup.addEventListener('click', restartPlan);
  restartBtnMain.addEventListener('click', restartPlan);

  savePlanBtn.addEventListener('click', async () => {
    clearErrors();
    const n = parseInt(photoPlanInput.value, 10);
    if (isNaN(n) || n < 1 || n > 10) {
      setupError.textContent = 'Please choose a number between 1 and 10.';
      show(setupError);
      return;
    }
    const r = await api('/set_photo_plan', 'POST', { planCount: n });
    if (!r.ok) {
      setupError.textContent = `Error: ${r.error}`;
      show(setupError);
      return;
    }
    await refreshMe();
  });

  captureBtn.addEventListener('click', async () => {
    clearErrors();
    todayThumb.innerHTML = '';
    loader.style.display = 'block';
    captureBtn.disabled = true;


    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageDataURL = canvas.toDataURL('image/jpeg');

    const r = await api('/capture', 'POST', { image: imageDataURL });
    loader.style.display = 'none';

    if (!r.ok) {

      if (r.error === 'Not same person') {
        const simText = (typeof r.similarity === 'number') ? ` (similarity ${ (r.similarity*100).toFixed(2) }%)` : '';
        mainError.textContent = `Capture rejected: not the same person${simText}. Please position the original person and try again.`;
        show(mainError);
      } else if (r.error === 'Capture locked' && typeof r.remaining_seconds === 'number') {
        mainError.textContent = `Please wait: next capture in ${fmtTime(r.remaining_seconds)}.`;
        show(mainError);
      } else {
        mainError.textContent = `Error: ${r.error || 'Unknown error'}`;
        show(mainError);
      }
      captureBtn.disabled = false;
      await refreshMe();
      return;
    }


    const img = document.createElement('img');
    img.src = `${r.image_url}?t=${Date.now()}`;
    img.className = 'thumbnail-img';
    todayThumb.appendChild(img);


    if (r.done) {
      me = await api('/me');
    }

    await refreshMe();
  });


  refreshMe();
});