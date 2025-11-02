export const Card = ({ children, className = '', hover = false, onClick }) => {
  const baseStyles = 'bg-black/50 border border-white/10 rounded-lg transition-colors';
  const hoverStyles = hover ? 'hover:bg-white/5 cursor-pointer' : '';

  return (
    <div
      className={`${baseStyles} ${hoverStyles} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
};
