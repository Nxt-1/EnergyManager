// Namespaced HA card. The URL is the authenticated ingress path selected by the installer.
class EnergyManagerCard extends HTMLElement {
  setConfig(config) {
    if (!config.url?.startsWith('/api/hassio_ingress/')) throw new Error(
      'Configure an authenticated EnergyManager 4 ingress URL');
    this.config = config;
  }
  connectedCallback() {
    if (this.querySelector('iframe') || !this.config) return;
    const frame = document.createElement('iframe');
    frame.src = this.config.url;
    frame.title = 'EnergyManager 4';
    frame.style = 'width:100%;height:90vh;border:0;border-radius:10px';
    this.append(frame);
  }
  getCardSize() {
    return 12
  }
}
if (!customElements.get('energymanager-card')) customElements.define('energymanager-card',
  EnergyManagerCard);
