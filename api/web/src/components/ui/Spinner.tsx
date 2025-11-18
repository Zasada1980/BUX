import './Spinner.css';

interface SpinnerProps {
  size?: 'small' | 'medium' | 'large';
  text?: string;
}

export default function Spinner({ size = 'medium', text }: SpinnerProps) {
  return (
    <div className="spinner-container">
      <div className={`spinner spinner-${size}`}></div>
      {text && <p className="spinner-text">{text}</p>}
    </div>
  );
}
