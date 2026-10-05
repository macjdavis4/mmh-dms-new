/** Decorative line illustration of a counterbalance forklift (original artwork). */
export function ForkliftArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 420 300" className={className} aria-hidden="true" fill="none">
      <g stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round">
        {/* mast */}
        <path d="M300 40v190M326 40v190M300 70h26M300 150h26" />
        {/* carriage and forks */}
        <path d="M326 170h14v60M340 230h62" />
        {/* body */}
        <path d="M110 230V160c0-12 8-20 20-20h70l40-60h40v150" />
        <path d="M110 230h190" />
        {/* overhead guard */}
        <path d="M200 140l20-80h60" />
        {/* counterweight */}
        <path d="M110 160H84c-10 0-16 8-16 18v52h42" />
        {/* seat and wheel */}
        <path d="M200 140v-24h-26" />
        <path d="M236 108l22 8" />
      </g>
      <circle cx="140" cy="236" r="30" stroke="currentColor" strokeWidth="6" />
      <circle cx="140" cy="236" r="10" fill="currentColor" />
      <circle cx="270" cy="240" r="24" stroke="currentColor" strokeWidth="6" />
      <circle cx="270" cy="240" r="8" fill="currentColor" />
      <path d="M20 270h380" stroke="currentColor" strokeWidth="3" strokeDasharray="10 12" opacity="0.4" />
      <rect x="346" y="186" width="54" height="40" rx="3" fill="#FFB000" opacity="0.9" />
      <path d="M346 206h54M373 186v40" stroke="#0B2A4A" strokeWidth="2" opacity="0.45" />
    </svg>
  );
}
