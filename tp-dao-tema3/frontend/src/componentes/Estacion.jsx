// Ilustración decorativa del login: una estación espacial esférica
// ("la Estrella de la Mercadería"), dibujada en SVG con los colores del sistema.
// Solo decoración: no tiene lógica.
export default function Estacion({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 400 400" aria-hidden="true">
      <defs>
        <radialGradient id="est-casco" cx="38%" cy="32%" r="75%">
          <stop offset="0%" stopColor="#8a7258" />
          <stop offset="45%" stopColor="#5a4532" />
          <stop offset="85%" stopColor="#2e2118" />
          <stop offset="100%" stopColor="#1f160f" />
        </radialGradient>
        <radialGradient id="est-plato" cx="40%" cy="40%" r="70%">
          <stop offset="0%" stopColor="#3a2a1e" />
          <stop offset="70%" stopColor="#6b5440" />
          <stop offset="100%" stopColor="#8a7258" />
        </radialGradient>
        <radialGradient id="est-nucleo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff6e0" />
          <stop offset="35%" stopColor="#f6c768" />
          <stop offset="100%" stopColor="#e0a83a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="est-halo" cx="50%" cy="50%" r="50%">
          <stop offset="70%" stopColor="#e0a83a" stopOpacity="0" />
          <stop offset="88%" stopColor="#e0a83a" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#e0a83a" stopOpacity="0" />
        </radialGradient>
        <clipPath id="est-esfera"><circle cx="200" cy="200" r="160" /></clipPath>
      </defs>

      {/* Halo */}
      <circle cx="200" cy="200" r="195" fill="url(#est-halo)" />

      {/* Casco */}
      <circle cx="200" cy="200" r="160" fill="url(#est-casco)" />

      <g clipPath="url(#est-esfera)" stroke="#b09c84" strokeOpacity="0.22" fill="none" strokeWidth="1">
        {/* Paralelos */}
        {[-120, -90, -60, -30, 30, 60, 90, 120].map((dy) => (
          <ellipse key={dy} cx="200" cy={200 + dy} rx={Math.sqrt(160 * 160 - dy * dy)} ry={10} />
        ))}
        {/* Meridianos */}
        {[40, 80, 120].map((rx) => <ellipse key={rx} cx="200" cy="200" rx={rx} ry="160" />)}
        {/* Paneles sueltos */}
        {[[120, 260, 26, 8], [250, 280, 34, 6], [280, 150, 22, 10], [160, 320, 30, 6], [300, 230, 18, 8],
          [90, 200, 20, 6], [230, 110, 26, 6], [320, 300, 16, 6]].map(([x, y, w, h], i) => (
          <rect key={i} x={x} y={y} width={w} height={h} fill="#1f160f" fillOpacity="0.35" stroke="none" />
        ))}
        {/* Luces de las ventanas */}
        {[[110, 250], [190, 300], [270, 260], [310, 180], [240, 340], [150, 330], [330, 260], [220, 270]].map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="1.6" fill="#f6c768" stroke="none" fillOpacity="0.8" />
        ))}
      </g>

      {/* Zanja del ecuador */}
      <g clipPath="url(#est-esfera)">
        <ellipse cx="200" cy="208" rx="162" ry="13" fill="#1a120c" />
        <ellipse cx="200" cy="204" rx="162" ry="11" fill="none" stroke="#e0a83a" strokeOpacity="0.35" strokeWidth="1" />
      </g>

      {/* Plato cóncavo con el núcleo encendido */}
      <circle cx="140" cy="128" r="44" fill="url(#est-plato)" />
      <circle cx="140" cy="128" r="44" fill="none" stroke="#1a120c" strokeWidth="3" />
      <g stroke="#2e2118" strokeWidth="1" strokeOpacity="0.8">
        {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
          <line key={a} x1="140" y1="128"
            x2={140 + 40 * Math.cos((a * Math.PI) / 180)} y2={128 + 40 * Math.sin((a * Math.PI) / 180)} />
        ))}
      </g>
      <circle className="estacion-nucleo" cx="140" cy="128" r="14" fill="url(#est-nucleo)" />

      {/* Sombra del lado oscuro */}
      <circle cx="200" cy="200" r="160" fill="none" stroke="#000" strokeOpacity="0.25" strokeWidth="2" />
    </svg>
  );
}
