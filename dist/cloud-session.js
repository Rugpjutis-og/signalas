"use strict";
window.SignalSession=(()=>{
  let csrf=null;
  const screen=document.getElementById('sign-in-screen'),form=document.getElementById('sign-in-form'),error=document.getElementById('sign-in-error');
  document.body.classList.add('signed-out');
  let resolve;
  const ready=new Promise(done=>{resolve=done;});
  function accept(data){csrf=data.csrf;screen.hidden=true;document.body.classList.remove('signed-out');resolve(data);}
  form.addEventListener('submit',async event=>{
    event.preventDefault();error.textContent='';
    const input=document.getElementById('sign-in-password'),submit=form.querySelector('button');submit.disabled=true;
    try{
      const response=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:input.value})});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Prisijungti nepavyko.');
      input.value='';accept(result);
    }catch(problem){error.textContent=problem.message;}finally{submit.disabled=false;}
  });
  (async()=>{
    try{
      const response=await fetch('/api/auth/session',{cache:'no-store'});const data=await response.json();
      if(!response.ok)throw Error(data.error||'Prisijungimo patikrinti nepavyko.');
      if(data.authenticated)accept(data);else screen.hidden=false;
    }catch(problem){screen.hidden=false;error.textContent=problem.message;}
  })();
  document.getElementById('sign-out').addEventListener('click',async()=>{
    await fetch('/api/auth/logout',{method:'POST',headers:{'X-Signalas-CSRF':csrf}});location.reload();
  });
  return Object.freeze({ready,csrf:()=>csrf});
})();
