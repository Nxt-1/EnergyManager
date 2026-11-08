import {localDateTime,localInstants} from './date-time.js';

export function rollingDates(now,zone) {
  const first = localDateTime(now,zone).slice(0,10);
  const origin = Date.parse(first+'T12:00:00Z');
  return Array.from({length:8},(_,index)=>new Date(origin+index*86400000).toISOString().slice(0,10));
}

export function tomorrowFinish(now,zone,hour) {
  const date = rollingDates(now,zone)[1];
  return localInstants(`${date}T${String(hour).padStart(2,'0')}:00`,zone)[0] || null;
}

export class ApplianceDeadline {
  constructor(root,changed,signal) {
    this.root=root; this.changed=changed; this.value=null; this.zone='Europe/Brussels'; this.now=Date.now();
    root.innerHTML=`<div class="appliance-finish-options"><button type="button" data-finish="12">Tomorrow 12:00</button>
      <button type="button" data-finish="18">Tomorrow 18:00</button><button type="button" data-custom-finish aria-label="Custom latest finish">▦</button></div>
      <p data-finish-summary>Choose latest finish</p><section data-finish-popup role="dialog" aria-label="Choose latest finish" hidden></section>`;
    root.addEventListener('click',event=>{
      const preset=event.target.closest('[data-finish]');
      if(preset) this.setValue(tomorrowFinish(this.now,this.zone,Number(preset.dataset.finish)),true);
      if(event.target.closest('[data-custom-finish]')) this.open();
      if(event.target.closest('[data-close-finish]')) root.querySelector('[data-finish-popup]').hidden=true;
      const day=event.target.closest('[data-finish-date]');
      if(day){this.draftDate=day.dataset.finishDate;this.selection();}
      if(event.target.closest('[data-apply-finish]')){
        const choices=localInstants(`${this.draftDate}T${this.hour}:${this.minute}`,this.zone);
        const offset=root.querySelector('[data-finish-offset]')?.value;
        const at=choices.length===1?choices[0]:offset;
        if(at){this.setValue(at,true);root.querySelector('[data-finish-popup]').hidden=true;}
      }
    },{signal});
    root.addEventListener('change',event=>{
      if(event.target.matches('[data-time-part]')){
        this[event.target.dataset.timePart]=event.target.value;
        event.target.closest('label').scrollIntoView({block:'center'});
        this.selection();
      }
      if(event.target.matches('[data-finish-offset]')) root.querySelector('[data-apply-finish]').disabled=!event.target.value;
    },{signal});
  }
  setContext(now,zone){this.now=Date.parse(now);this.zone=zone;}
  setValue(value,notify=false){
    this.value=value;
    this.root.querySelector('[data-finish-summary]').textContent=value?new Date(value).toLocaleString('en-GB',{timeZone:this.zone,timeZoneName:'shortOffset'}):'Choose latest finish';
    for(const button of this.root.querySelectorAll('[data-finish]'))button.setAttribute('aria-pressed',String(value===tomorrowFinish(this.now,this.zone,Number(button.dataset.finish))));
    if(notify)this.changed(value);
  }
  open(){
    const local=localDateTime(this.value || this.now+3600000,this.zone);
    this.draftDate=rollingDates(this.now,this.zone).includes(local.slice(0,10))?local.slice(0,10):rollingDates(this.now,this.zone)[0];
    [this.hour,this.minute]=local.slice(11).split(':');
    const panel=this.root.querySelector('[data-finish-popup]');panel.hidden=false;
    panel.innerHTML=`<div class="appliance-picker-head"><strong>Latest finish</strong><button type="button" data-close-finish aria-label="Close latest finish picker">×</button></div>
      <div class="appliance-picker-body"><div class="appliance-date-tiles">${rollingDates(this.now,this.zone).map(date=>{
        const day=new Date(date+'T12:00:00Z');
        return `<button type="button" data-finish-date="${date}"><span>${day.toLocaleDateString('en-GB',{weekday:'short',timeZone:'UTC'})}</span><strong>${day.getUTCDate()}</strong><span>${day.toLocaleDateString('en-GB',{month:'short',timeZone:'UTC'})}</span></button>`;
      }).join('')}</div><div class="appliance-time-wheels">${[['hour',24],['minute',60]].map(([part,count])=>`<div><span>${part==='hour'?'Hour':'Minute'}</span><div class="appliance-time-wheel" data-wheel="${part}">${Array.from({length:count},(_,index)=>{
        const value=String(index).padStart(2,'0');return `<label><input type="radio" name="appliance-${part}" data-time-part="${part}" value="${value}" ${this[part]===value?'checked':''}><span>${value}</span></label>`;
      }).join('')}</div></div>`).join('')}</div></div><div data-finish-validation></div><button type="button" data-apply-finish>Use latest finish</button>`;
    for(const part of ['hour','minute']){
      const wheel=panel.querySelector(`[data-wheel="${part}"]`);
      wheel.scrollTop=Number(this[part])*44;
      wheel.addEventListener('scroll',()=>{
        const index=Math.max(0,Math.min(part==='hour'?23:59,Math.round(wheel.scrollTop/44)));
        this[part]=String(index).padStart(2,'0');
        wheel.querySelector(`input[value="${this[part]}"]`).checked=true;this.selection();
      },{passive:true});
    }
    this.choiceSignature=null;this.selection();
  }
  selection(){
    for(const day of this.root.querySelectorAll('[data-finish-date]'))day.setAttribute('aria-pressed',String(day.dataset.finishDate===this.draftDate));
    const choices=localInstants(`${this.draftDate}T${this.hour}:${this.minute}`,this.zone);
    const validation=this.root.querySelector('[data-finish-validation]');
    const signature=JSON.stringify(choices);
    if(signature!==this.choiceSignature){
      this.choiceSignature=signature;
      validation.innerHTML=choices.length===0?'This local time does not exist because the clock changes.':choices.length===2?
        `<label>Repeated local time<select data-finish-offset><option value="">Choose occurrence</option>${choices.map((at,index)=>`<option value="${at}">${index===0?'First':'Second'} · ${new Date(at).toLocaleTimeString('en-GB',{timeZone:this.zone,timeZoneName:'shortOffset'})}</option>`).join('')}</select></label>`:'';
    }
    this.root.querySelector('[data-apply-finish]').disabled=choices.length!==1 && !this.root.querySelector('[data-finish-offset]')?.value;
  }
}
