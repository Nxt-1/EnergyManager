import {mountApplication} from './application-view.js';

const response = await fetch(new URL('./view.html', import.meta.url));
if (!response.ok) throw new Error('EnergyManager interface could not be loaded');
document.body.innerHTML = await response.text();
await mountApplication(document);
