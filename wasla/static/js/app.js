(function(){
  // Tabs
  document.querySelectorAll("[data-tab]").forEach(function(btn){
    btn.addEventListener("click", function(){
      var target = btn.getAttribute("data-tab");
      document.querySelectorAll("[data-tab]").forEach(b=>b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll("[data-pane]").forEach(function(p){
        p.style.display = (p.getAttribute("data-pane") === target) ? "block" : "none";
      });
    });
  });

  // OTP auto-advance
  var otpInputs = document.querySelectorAll(".otp input");
  if(otpInputs.length){
    otpInputs[0].focus();
    otpInputs.forEach(function(inp, idx){
      inp.addEventListener("input", function(){
        inp.value = inp.value.replace(/\D/g,'').slice(0,1);
        if(inp.value && idx < otpInputs.length-1){
          otpInputs[idx+1].focus();
        }
      });
      inp.addEventListener("keydown", function(e){
        if(e.key === "Backspace" && !inp.value && idx>0){
          otpInputs[idx-1].focus();
        }
      });
    });
    // paste support
    otpInputs[0].addEventListener("paste", function(e){
      var text = (e.clipboardData || window.clipboardData).getData("text");
      if(!text) return;
      var digits = text.replace(/\D/g,'').slice(0, otpInputs.length).split('');
      digits.forEach((d,i)=> otpInputs[i].value = d);
      if(digits.length === otpInputs.length){
        otpInputs[otpInputs.length-1].focus();
      }
      e.preventDefault();
    });
  }
})();