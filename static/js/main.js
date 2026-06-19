/* FindIt v2 — main.js */
const savedTheme = localStorage.getItem('fi-theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
function updateBtn() {
  const b = document.getElementById('theme-btn');
  if (b) b.innerHTML = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';
}
function toggleTheme() {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('fi-theme', next);
  updateBtn();
}

function initOtp() {
  const boxes = document.querySelectorAll('.otp-box');
  const hidden = document.getElementById('otp-hidden');
  if (!boxes.length) return;
  const sync = () => { if (hidden) hidden.value = [...boxes].map(b => b.value).join(''); };
  boxes.forEach((box, i) => {
    box.addEventListener('input', () => {
      box.value = box.value.replace(/\D/g,'').slice(-1);
      if (box.value && i < boxes.length-1) boxes[i+1].focus();
      sync();
    });
    box.addEventListener('keydown', e => { if (e.key==='Backspace' && !box.value && i>0) boxes[i-1].focus(); });
    box.addEventListener('paste', e => {
      e.preventDefault();
      const digits = (e.clipboardData||window.clipboardData).getData('text').replace(/\D/g,'');
      [...digits].slice(0,boxes.length).forEach((ch,j) => { boxes[j].value = ch; });
      sync();
      boxes[Math.min(digits.length, boxes.length-1)].focus();
    });
  });
}

function initPw() {
  const pw = document.getElementById('password');
  const bar = document.getElementById('pw-bar');
  const hint = document.getElementById('pw-hint');
  if (!pw || !bar) return;
  pw.addEventListener('input', () => {
    let s = 0;
    if (pw.value.length >= 8) s++;
    if (/[A-Z]/.test(pw.value)) s++;
    if (/[0-9]/.test(pw.value)) s++;
    if (/[^A-Za-z0-9]/.test(pw.value)) s++;
    bar.className = 'pw-bar';
    if (s <= 1) { bar.classList.add('weak'); if(hint) hint.textContent='Weak — add numbers & uppercase'; }
    else if (s <= 2) { bar.classList.add('medium'); if(hint) hint.textContent='Medium'; }
    else { bar.classList.add('strong'); if(hint) hint.textContent='Strong ✓'; }
  });
}

let chatOpen = false, chatHist = [];
const chatSid = 's_' + Math.random().toString(36).substr(2, 9);
function toggleChat() {
  chatOpen = !chatOpen;
  const w = document.getElementById('chat-win');
  if (w) w.classList.toggle('open', chatOpen);
  if (chatOpen && chatHist.length === 0) addBot("Hi! 👋 I'm FindIt Assistant. Tell me what you've lost or found and I'll help!");
  if (chatOpen) { const inp = document.getElementById('chat-in'); if(inp) setTimeout(()=>inp.focus(),100); }
}
function addBot(t) {
  const m = document.getElementById('chat-msgs'); if(!m) return;
  const d = document.createElement('div'); d.className = 'cmsg bot'; d.textContent = t;
  m.appendChild(d); m.scrollTop = m.scrollHeight;
}
function addUser(t) {
  const m = document.getElementById('chat-msgs'); if(!m) return;
  const d = document.createElement('div'); d.className = 'cmsg usr'; d.textContent = t;
  m.appendChild(d); m.scrollTop = m.scrollHeight;
}
function showTyping() {
  const m = document.getElementById('chat-msgs'); if(!m) return null;
  const d = document.createElement('div'); d.className = 'cmsg bot typing'; d.id = 'typing-ind';
  d.innerHTML = '<span>●</span><span>●</span><span>●</span>';
  m.appendChild(d); m.scrollTop = m.scrollHeight; return d;
}
async function sendChat() {
  const inp = document.getElementById('chat-in'); if(!inp) return;
  const txt = inp.value.trim(); if(!txt) return;
  inp.value = ''; addUser(txt); chatHist.push({role:'user', content:txt});
  const t = showTyping();
  try {
    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:txt, history:chatHist, session_id:chatSid})});
    const d = await r.json(); if(t) t.remove();
    const rep = d.reply || "Sorry, couldn't process that. Try again.";
    addBot(rep); chatHist.push({role:'assistant', content:rep});
  } catch { if(t) t.remove(); addBot("Connection error. Please try again."); }
}

let sugTimer = null;
async function doSuggest() {
  const title = document.getElementById('title')?.value?.trim();
  const desc = document.getElementById('description')?.value?.trim();
  const type = document.querySelector('input[name="type"]:checked')?.value || 'lost';
  const box = document.getElementById('ai-box');
  if (!box || !title || title.length < 3) return;
  clearTimeout(sugTimer);
  sugTimer = setTimeout(async () => {
    try {
      const r = await fetch('/api/suggest', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({title, description:desc, type})});
      const d = await r.json();
      if (d.suggestion) {
        box.innerHTML = '<strong>✨ AI Suggestion:</strong> ' + d.suggestion +
          ' <button onclick="useSug()" style="margin-left:.6rem;background:var(--teal);color:#fff;border:none;border-radius:50px;padding:.2rem .8rem;font-size:.73rem;cursor:pointer">Use this</button>';
        box._s = d.suggestion; box.style.display = 'block';
      }
    } catch {}
  }, 1200);
}
function useSug() {
  const box = document.getElementById('ai-box');
  const desc = document.getElementById('description');
  if (box && desc && box._s) { desc.value = box._s; box.style.display = 'none'; }
}

function initFlash() {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => { el.style.transition = 'opacity .5s'; el.style.opacity = '0'; setTimeout(()=>el.remove(),500); }, 5000);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  updateBtn(); initOtp(); initPw(); initFlash();
  const inp = document.getElementById('chat-in');
  if (inp) inp.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();} });
  const sb = document.getElementById('chat-send'); if(sb) sb.addEventListener('click', sendChat);
  const ti = document.getElementById('title'); if(ti) ti.addEventListener('input', doSuggest);
});
