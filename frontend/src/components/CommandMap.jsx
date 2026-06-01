import React, { useState } from 'react';

// Mumbai Coordinates for SVG Viewport mapping
// Center: (19.0760, 72.8777)
const ZONE_MAPPINGS = {
  "Dharavi": { x: 120, y: 310, lat: 19.0033, lon: 72.8446 },
  "Kurla": { x: 180, y: 190, lat: 19.0666, lon: 72.8562 },
  "Andheri": { x: 130, y: 110, lat: 19.1190, lon: 72.8465 },
  "Command": { x: 250, y: 180, lat: 19.0760, lon: 72.8777 }
};

export default function CommandMap({ world, routes }) {
  const [hoveredZone, setHoveredZone] = useState(null);

  // Fallback if zones are empty
  const zones = world?.zones || [
    { name: "Dharavi", casualties: 200, critical: 24, serious: 56, ambulances_deployed: 4, response_delay_min: 15, access: "open" },
    { name: "Kurla", casualties: 150, critical: 18, serious: 42, ambulances_deployed: 3, response_delay_min: 22, access: "open" },
    { name: "Andheri", casualties: 100, critical: 12, serious: 28, ambulances_deployed: 2, response_delay_min: 18, access: "open" }
  ];

  const getRouteForZone = (zoneName) => {
    if (!routes || !routes.routes) return null;
    return routes.routes.find(r => r.zone === zoneName);
  };

  return (
    <div className="map-placeholder">
      {/* Dark Vector Grid */}
      <svg width="100%" height="100%" viewBox="0 0 400 440" style={{ background: '#131317' }}>
        <defs>
          <radialGradient id="hubGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FFD15C" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#FFD15C" stopOpacity="0" />
          </radialGradient>
          {zones.map((z) => {
            const mapPos = ZONE_MAPPINGS[z.name] || { x: 200, y: 200 };
            const critical = parseInt(z.critical || 0);
            const riskRadius = Math.min(60, 20 + critical * 1.5);
            return (
              <radialGradient key={`grad-${z.name}`} id={`glow-${z.name}`} cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#FF5A36" stopOpacity="0.35" />
                <stop offset="60%" stopColor="#FF3E1B" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#FF3E1B" stopOpacity="0" />
              </radialGradient>
            );
          })}
        </defs>

        {/* Coordinate Lines */}
        <g stroke="rgba(255,255,255,0.03)" strokeWidth="1">
          <line x1="50" y1="0" x2="50" y2="440" />
          <line x1="100" y1="0" x2="100" y2="440" />
          <line x1="150" y1="0" x2="150" y2="440" />
          <line x1="200" y1="0" x2="200" y2="440" />
          <line x1="250" y1="0" x2="250" y2="440" />
          <line x1="300" y1="0" x2="300" y2="440" />
          <line x1="350" y1="0" x2="350" y2="440" />
          
          <line x1="0" y1="50" x2="400" y2="50" />
          <line x1="0" y1="100" x2="400" y2="100" />
          <line x1="0" y1="150" x2="400" y2="150" />
          <line x1="0" y1="200" x2="400" y2="200" />
          <line x1="0" y1="250" x2="400" y2="250" />
          <line x1="0" y1="300" x2="400" y2="300" />
          <line x1="0" y1="350" x2="400" y2="350" />
          <line x1="0" y1="400" x2="400" y2="400" />
        </g>

        {/* Route Lines (Command Center -> Zones) */}
        {zones.map((z) => {
          const mapPos = ZONE_MAPPINGS[z.name];
          const hubPos = ZONE_MAPPINGS["Command"];
          if (!mapPos) return null;

          const route = getRouteForZone(z.name);
          const isBlocked = route?.status === 'blocked' || z.access === 'blocked';
          const strokeColor = isBlocked ? '#FF3E1B' : '#FF5A36';
          const strokeDash = isBlocked ? '6,6' : 'none';

          return (
            <g key={`route-${z.name}`}>
              {/* Secondary route glow */}
              <line 
                x1={hubPos.x} y1={hubPos.y} 
                x2={mapPos.x} y2={mapPos.y} 
                stroke={strokeColor} 
                strokeWidth="4" 
                strokeOpacity="0.15" 
              />
              <line 
                x1={hubPos.x} y1={hubPos.y} 
                x2={mapPos.x} y2={mapPos.y} 
                stroke={strokeColor} 
                strokeWidth="1.5" 
                strokeDasharray={strokeDash}
                strokeOpacity="0.8" 
              />
            </g>
          );
        })}

        {/* Zone Risk Waves (Glow) */}
        {zones.map((z) => {
          const mapPos = ZONE_MAPPINGS[z.name];
          if (!mapPos) return null;

          const critical = parseInt(z.critical || 0);
          const riskRadius = Math.min(80, 24 + critical * 1.6);

          return (
            <circle
              key={`glow-circle-${z.name}`}
              cx={mapPos.x}
              cy={mapPos.y}
              r={riskRadius}
              fill={`url(#glow-${z.name})`}
            />
          );
        })}

        {/* Zone Markers (Interactive) */}
        {zones.map((z) => {
          const mapPos = ZONE_MAPPINGS[z.name];
          if (!mapPos) return null;

          const critical = parseInt(z.critical || 0);
          const activeColor = hoveredZone === z.name ? '#FF5A36' : '#FF3E1B';

          return (
            <g 
              key={`marker-${z.name}`} 
              onMouseEnter={() => setHoveredZone(z)}
              onMouseLeave={() => setHoveredZone(null)}
              style={{ cursor: 'pointer' }}
            >
              {/* Hover highlight circle */}
              <circle
                cx={mapPos.x}
                cy={mapPos.y}
                r="16"
                fill="transparent"
                stroke={hoveredZone === z.name ? 'rgba(255, 90, 54, 0.4)' : 'transparent'}
                strokeWidth="1.5"
              />
              
              {/* Zone core dot */}
              <circle
                cx={mapPos.x}
                cy={mapPos.y}
                r={hoveredZone === z.name ? "7" : "5"}
                fill={activeColor}
                stroke="#FFFFFF"
                strokeWidth="1.5"
                style={{ transition: 'all 0.15s ease' }}
              />

              {/* Text Label */}
              <text
                x={mapPos.x}
                y={mapPos.y - 12}
                fill="#FFFFFF"
                fontSize="11"
                fontWeight="600"
                fontFamily="'Inter', sans-serif"
                textAnchor="middle"
                style={{ textShadow: '0px 1px 4px rgba(0,0,0,0.8)' }}
              >
                {z.name}
              </text>
            </g>
          );
        })}

        {/* Command Center Hub */}
        <g>
          <circle 
            cx={ZONE_MAPPINGS.Command.x} 
            cy={ZONE_MAPPINGS.Command.y} 
            r="28" 
            fill="url(#hubGlow)" 
          />
          <circle 
            cx={ZONE_MAPPINGS.Command.x} 
            cy={ZONE_MAPPINGS.Command.y} 
            r="6" 
            fill="#111111" 
            stroke="#FFD15C" 
            strokeWidth="2.5" 
          />
          <text
            x={ZONE_MAPPINGS.Command.x}
            y={ZONE_MAPPINGS.Command.y - 12}
            fill="#FFD15C"
            fontSize="10"
            fontWeight="700"
            fontFamily="'Inter', sans-serif"
            textAnchor="middle"
            style={{ letterSpacing: '0.5px', textShadow: '0 1px 3px rgba(0,0,0,0.8)' }}
          >
            COMMAND CENTER
          </text>
        </g>
      </svg>

      {/* Dynamic Hover Tooltip Layer */}
      {hoveredZone && (
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          backgroundColor: '#131317',
          color: '#FFFFFF',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px solid rgba(255,255,255,0.1)',
          boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          fontSize: '13px',
          pointerEvents: 'none',
          zIndex: 10,
          fontFamily: "'Inter', sans-serif"
        }}>
          <div style={{ fontWeight: '700', fontSize: '14px', marginBottom: '6px', color: '#FF5A36' }}>{hoveredZone.name}</div>
          <div>Casualties: <strong style={{ color: '#fff' }}>{hoveredZone.casualties}</strong></div>
          <div>Critical: <strong style={{ color: '#FF3E1B' }}>{hoveredZone.critical}</strong></div>
          <div>Ambulances: <strong style={{ color: '#fff' }}>{hoveredZone.ambulances_deployed}</strong></div>
          <div>Response Delay: <strong style={{ color: '#FFD15C' }}>{hoveredZone.response_delay_min} min</strong></div>
          <div style={{ textTransform: 'capitalize' }}>Access Corridor: <strong>{hoveredZone.access}</strong></div>
        </div>
      )}

      {/* Bottom map metadata legend */}
      <div style={{
        position: 'absolute',
        bottom: '12px',
        right: '12px',
        display: 'flex',
        gap: '12px',
        backgroundColor: 'rgba(19, 19, 23, 0.85)',
        padding: '6px 12px',
        borderRadius: '6px',
        fontSize: '11px',
        fontWeight: '500',
        color: '#aaaaaa',
        fontFamily: "'Inter', sans-serif"
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#FF3E1B', display: 'inline-block' }}></span>
          <span>Casualty Zone</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#111', border: '1.5px solid #FFD15C', display: 'inline-block' }}></span>
          <span>Logistics Hub</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '12px', height: '1.5px', backgroundColor: '#FF5A36', display: 'inline-block' }}></span>
          <span>Corridor</span>
        </div>
      </div>
    </div>
  );
}
