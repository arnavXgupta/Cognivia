export const Input = ({
  type = 'text',
  placeholder,
  icon: Icon,
  className = '',
  ...props
}) => {
  return (
    <div className="relative w-full">
      {Icon && (
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-white/60">
          <Icon className="w-5 h-5" />
        </div>
      )}
      <input
        type={type}
        placeholder={placeholder}
        className={`w-full rounded-lg border border-white/20 bg-black/50 px-4 py-3 text-white placeholder:text-white/60 focus:border-white/50 focus:outline-none focus:ring-0 transition-colors ${Icon ? 'pl-11' : ''} ${className}`}
        {...props}
      />
    </div>
  );
};
