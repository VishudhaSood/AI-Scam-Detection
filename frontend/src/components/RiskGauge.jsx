import React from 'react';

const RiskGauge = ({ score }) => {
  // score is a float between 0.0 and 1.0
  const percentage = Math.round(score * 100);
  
  // SVG Circle calculations
  const radius = 60;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  // Determine color based on threshold
  let strokeColor = 'var(--color-safe)';
  if (score > 0.3 && score <= 0.7) {
    strokeColor = 'var(--color-suspicious)';
  } else if (score > 0.7) {
    strokeColor = 'var(--color-scam)';
  }

  return (
    <div style={{ position: 'relative', width: '160px', height: '160px', margin: '0 auto' }}>
      <svg width="100%" height="100%" viewBox="0 0 160 160" style={{ transform: 'rotate(-90deg)' }}>
        {/* Track circle (background) */}
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="transparent"
          stroke="var(--bg-tertiary)"
          strokeWidth={strokeWidth}
        />
        {/* Active colored indicator arc */}
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="transparent"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{
            transition: 'stroke-dashoffset 1s ease-in-out',
            filter: `drop-shadow(0 0 6px ${strokeColor}70)`
          }}
        />
      </svg>
      {/* Centered textual score indicator */}
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        textAlign: 'center'
      }}>
        <div style={{ 
          fontSize: '2rem', 
          fontWeight: '700', 
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-mono)',
          lineHeight: '1.2'
        }}>
          {percentage}%
        </div>
        <div style={{ 
          fontSize: '0.7rem', 
          textTransform: 'uppercase', 
          color: 'var(--text-secondary)',
          letterSpacing: '1px'
        }}>
          Threat Level
        </div>
      </div>
    </div>
  );
};

export default RiskGauge;
