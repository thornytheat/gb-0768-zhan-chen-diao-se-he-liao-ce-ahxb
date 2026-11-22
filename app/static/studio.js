const parcel = document.querySelector('#parcel');
const order = document.querySelector('#job-form');
const note = document.querySelector('#studio-feedback');
function target(sample, key) {
  const url = new URL(location.href);
  url.searchParams.set('sample', sample);
  if (key) url.searchParams.set('key', key);
  else url.searchParams.delete('key');
  return url;
}
parcel.addEventListener('change', () => location.assign(target(parcel.value)));
document.querySelector('#print-receipt').addEventListener('click', () => window.print());
order.addEventListener('submit', async event => {
  event.preventDefault();
  const button = order.querySelector('[type=submit]');
  button.disabled = true;
  note.hidden = false;
  note.textContent = '正在封存秤单';
  try {
    const response = await fetch('/api/books', {method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({sample: parcel.value})});
    const saved = await response.json();
    if (!response.ok) throw new Error(saved.message);
    const next = target(parcel.value, saved.key);
    if (next.href === location.href) note.textContent = '同一收据留档已复用';
    else location.assign(next);
  } catch (error) {
    note.textContent = error.message || '封存失败，请重试';
  } finally {
    button.disabled = false;
  }
});
const pots = document.querySelector('#pot-filter');
pots?.addEventListener('change', () => {
  for (const row of document.querySelectorAll('#pot-lines tr')) {
    row.hidden = pots.value !== 'all' && row.dataset.pot !== pots.value;
  }
});

async function deskAction(url, body, feedback) {
  const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message);
  return result;
}

const desk = document.querySelector('.desk-actions');
if (desk) {
  const key = new URL(location.href).searchParams.get('key');
  const feedback = document.querySelector('#studio-feedback');
  document.addEventListener('click', async event => {
    const button = event.target.closest('button.desk-sign,button.desk-review');
    if (!button) return;
    const pot = button.dataset.pot;
    const path = button.classList.contains('desk-sign') ? 'sign' : 'review';
    const payload = path === 'sign' ? {pot} : {pot, decision: button.dataset.decision};
    button.disabled = true;
    feedback.hidden = false;
    feedback.textContent = '正在提交';
    try {
      const result = await deskAction(`/api/desk/${key}/${path}`, payload, feedback);
      feedback.textContent = result.reused ? '同一结论已存在，未重复出件' : '操作已留档';
      location.reload();
    } catch (error) {
      feedback.textContent = error.message || '操作失败，请重试';
      button.disabled = false;
    }
  });
}
