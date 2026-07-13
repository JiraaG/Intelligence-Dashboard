import { Directive, ElementRef, OnInit, inject } from '@angular/core';

@Directive({
  selector: '[appLeafletHatch]',
  standalone: true
})
export class LeafletHatchDirective implements OnInit {
  private readonly el = inject(ElementRef);

  ngOnInit(): void {
    // Individua l'elemento SVG nativo di Leaflet una volta disponibile nel DOM
    const observer = new MutationObserver(() => {
      const svg = this.el.nativeElement.querySelector('.leaflet-overlay-pane svg');
      if (svg) {
        this.injectSvgPatterns(svg as SVGElement);
        observer.disconnect();
      }
    });
    observer.observe(this.el.nativeElement, { childList: true, subtree: true });
  }

  private injectSvgPatterns(svg: SVGElement): void {
    let defs = svg.querySelector('defs');
    if (!defs) {
      defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      svg.insertBefore(defs, svg.firstChild);
    }

    // Definizione dei pattern geometrici associati alle 12 macro-categorie
    const patterns = [
      { id: 'hatch-nucleare', angle: 45, color: 'var(--color-nucleare)' },
      { id: 'hatch-acqua', angle: 0, color: 'var(--color-acqua)' },
      { id: 'hatch-energia', angle: 30, color: 'var(--color-energia)' },
      { id: 'hatch-infrastrutture', angle: 60, color: 'var(--color-infrastrutture)' },
      { id: 'hatch-geopolitica', angle: 15, color: 'var(--color-geopolitica)' },
      { id: 'hatch-economia', angle: 75, color: 'var(--color-economia)' },
      { id: 'hatch-tecnologia', angle: 90, color: 'var(--color-tecnologia)' },
      { id: 'hatch-scienza', angle: 105, color: 'var(--color-scienza)' },
      { id: 'hatch-spazio', angle: 120, color: 'var(--color-spazio)' },
      { id: 'hatch-ambiente', angle: 135, color: 'var(--color-ambiente)' },
      { id: 'hatch-salute', angle: 150, color: 'var(--color-salute)' },
      { id: 'hatch-sicurezza', angle: 165, color: 'var(--color-sicurezza)' }
    ];

    patterns.forEach(p => {
      if (defs!.querySelector(`#${p.id}`)) return;

      const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
      pattern.setAttribute('id', p.id);
      pattern.setAttribute('width', '12');
      pattern.setAttribute('height', '12');
      pattern.setAttribute('patternUnits', 'userSpaceOnUse');

      // Riempimento di sfondo semitrasparente per dare volume visivo
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('width', '12');
      rect.setAttribute('height', '12');
      rect.setAttribute('fill', p.color);
      rect.setAttribute('opacity', '0.10');
      pattern.appendChild(rect);

      // Linea diagonale geometrica di hatching
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', '6'); line.setAttribute('y1', '-6');
      line.setAttribute('x2', '6'); line.setAttribute('y2', '18');
      line.setAttribute('transform', `rotate(${p.angle}, 6, 6)`);
      line.setAttribute('stroke', p.color);
      line.setAttribute('stroke-width', '1.8');
      line.setAttribute('opacity', '0.65');
      pattern.appendChild(line);

      defs!.appendChild(pattern);
    });
  }
}
