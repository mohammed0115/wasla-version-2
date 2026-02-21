(function(){
  var mock = document.getElementById('mockCard');
  if (!mock) return;

  var svg = mock.querySelector('.flow-svg');
  if (!svg) return;

  var dots = Array.prototype.slice.call(svg.querySelectorAll('.flow-dot'));

  var steps = [
    { key: 'create', chip: '[data-ai-chip="create"]', target: '[data-flow-target="create"]' },
    { key: 'desc', chip: '[data-ai-chip="desc"]', target: '[data-flow-target="desc"]' },
    { key: 'search', chip: '[data-ai-chip="search"]', target: '[data-flow-target="search"]' },
    { key: 'domains', chip: '[data-ai-chip="domains"]', target: '[data-flow-target="domains"]' }
  ];

  var state = {
    t0: performance.now(),
    speed: [0.00020, 0.00016, 0.00014],
    phase: [0.00, 0.34, 0.67],
    active: 0,
    lastSwap: performance.now()
  };

  function setActive(idx){
    state.active = idx;

    var activeChips = document.querySelectorAll('.ai-chip.is-active');
    for (var i = 0; i < activeChips.length; i++) {
      activeChips[i].classList.remove('is-active');
    }

    var activeTargets = document.querySelectorAll('[data-flow-target].is-active');
    for (var j = 0; j < activeTargets.length; j++) {
      activeTargets[j].classList.remove('is-active');
    }

    var step = steps[idx];
    var chipEl = document.querySelector(step.chip);
    var targetEl = document.querySelector(step.target);

    if (chipEl) chipEl.classList.add('is-active');
    if (targetEl) targetEl.classList.add('is-active');
  }

  var chips = document.getElementById('chips');
  if (chips) {
    chips.addEventListener('click', function(e){
      var chip = e.target.closest('.ai-chip');
      if (!chip) return;
      var key = chip.getAttribute('data-ai-chip');
      var idx = -1;
      for (var i = 0; i < steps.length; i++) {
        if (steps[i].key === key) {
          idx = i;
          break;
        }
      }
      if (idx >= 0) {
        state.lastSwap = performance.now();
        setActive(idx);
      }
    });
  }

  setActive(0);

  function pointOnPath(path, t){
    var len = path.getTotalLength();
    var p = path.getPointAtLength(len * t);
    return { x: p.x, y: p.y };
  }

  var reducedMotion = false;
  if (window.matchMedia) {
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  if (reducedMotion) {
    return;
  }

  function render(now){
    if (now - state.lastSwap > 2400){
      state.lastSwap = now;
      setActive((state.active + 1) % steps.length);
    }

    for (var i = 0; i < dots.length; i++) {
      var dot = dots[i];
      var pathId = dot.getAttribute('data-path');
      var path = svg.querySelector('#' + pathId);
      if (!path) continue;

      var dt = (now - state.t0);
      var t = (dt * state.speed[i] + state.phase[i]) % 1;

      var p = pointOnPath(path, t);
      dot.setAttribute('cx', p.x);
      dot.setAttribute('cy', p.y);

      var nearEnd = t > 0.92;
      dot.style.transform = nearEnd ? 'scale(1.25)' : 'scale(1)';
      dot.style.opacity = nearEnd ? '1' : '.92';
    }

    requestAnimationFrame(render);
  }

  requestAnimationFrame(render);
})();
