import React from "react";

interface IconProps {
  className?: string;
}

const baseProps = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true as const
};

export const MicIcon: React.FC<IconProps> = ({ className = "w-8 h-8" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" x2="12" y1="19" y2="22" />
    <line x1="8" x2="16" y1="22" y2="22" />
  </svg>
);

export const VolumeIcon: React.FC<IconProps> = ({ className = "w-6 h-6" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
  </svg>
);

export const VolumeMutedIcon: React.FC<IconProps> = ({ className = "w-6 h-6" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <line x1="22" x2="16" y1="9" y2="15" />
    <line x1="16" x2="22" y1="9" y2="15" />
  </svg>
);

export const ChevronRightIcon: React.FC<IconProps> = ({ className = "w-6 h-6" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="m9 18 6-6-6-6" />
  </svg>
);

export const ArrowLeftIcon: React.FC<IconProps> = ({ className = "w-6 h-6" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="m12 19-7-7 7-7" />
    <path d="M19 12H5" />
  </svg>
);

export const AlertTriangleIcon: React.FC<IconProps> = ({ className = "w-8 h-8" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </svg>
);

export const PhoneIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92Z" />
  </svg>
);

export const ShareIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" x2="15.42" y1="13.51" y2="17.49" />
    <line x1="15.41" x2="8.59" y1="6.51" y2="10.49" />
  </svg>
);

export const ThumbsUpIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M7 10v12" />
    <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z" />
  </svg>
);

export const ThumbsDownIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M17 14V2" />
    <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z" />
  </svg>
);

export const ReplayIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
  </svg>
);

export const WifiOffIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <line x1="2" x2="22" y1="2" y2="22" />
    <path d="M8.5 16.5a5 5 0 0 1 7 0" />
    <path d="M2 8.82a15 15 0 0 1 4.17-2.65" />
    <path d="M10.66 5c4.01-.36 8.14.9 11.34 3.76" />
    <path d="M16.85 11.25a10 10 0 0 1 2.22 1.68" />
    <path d="M5 12.859a10 10 0 0 1 5.17-2.69" />
    <line x1="12" x2="12.01" y1="20" y2="20" />
  </svg>
);

export const CheckCircleIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <circle cx="12" cy="12" r="10" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

export const StopIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
);

export const KeyboardIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <rect width="20" height="16" x="2" y="4" rx="2" />
    <path d="M6 8h.01" />
    <path d="M10 8h.01" />
    <path d="M14 8h.01" />
    <path d="M18 8h.01" />
    <path d="M8 12h.01" />
    <path d="M12 12h.01" />
    <path d="M16 12h.01" />
    <path d="M7 16h10" />
  </svg>
);

export const MapPinIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
    <circle cx="12" cy="10" r="3" />
  </svg>
);

export const ClipboardCheckIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <rect width="8" height="4" x="8" y="2" rx="1" ry="1" />
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <path d="m9 14 2 2 4-4" />
  </svg>
);

export const HelpCircleIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
    <path d="M12 17h.01" />
  </svg>
);

export const XCircleIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <circle cx="12" cy="12" r="10" />
    <path d="m15 9-6 6" />
    <path d="m9 9 6 6" />
  </svg>
);

export const PlayIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M7 5.25c0-.98 1.08-1.57 1.91-1.05l10.22 6.75c.75.49.75 1.61 0 2.1L8.91 19.8C8.08 20.32 7 19.73 7 18.75V5.25Z" />
  </svg>
);

export const PauseIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <rect x="6" y="5" width="4.5" height="14" rx="1.5" />
    <rect x="13.5" y="5" width="4.5" height="14" rx="1.5" />
  </svg>
);

export const ChevronDownIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const ShieldCheckIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

export const LockIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <rect width="16" height="11" x="4" y="11" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

export const UserIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

export const EyeIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export const EyeOffIcon: React.FC<IconProps> = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} {...baseProps}>
    <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
    <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c6.4 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
    <path d="M6.61 6.61A13.53 13.53 0 0 0 2 12s3.6 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
    <line x1="2" x2="22" y1="2" y2="22" />
  </svg>
);

export const TopicIcon: React.FC<{ icon: string; className?: string }> = ({
  icon,
  className = "w-7 h-7"
}) => {
  switch (icon) {
    // Malaria: two-colour mosquito line icon
    case "shield-plus":
    case "malaria":
      return (
        <svg viewBox="0 0 24 24" className={className} {...baseProps}>
          <ellipse cx="12" cy="12" rx="2.2" ry="4.5" stroke="#0F5C4A" />
          <circle cx="12" cy="6" r="1.6" stroke="#F5A623" />
          <path d="M12 4.4V2" stroke="#F5A623" />
          <path d="M10 10C6.5 7 3.5 7.5 3.5 10.2c0 2 3.2 2.6 6.3 1.3" stroke="#0F5C4A" />
          <path d="M14 10c3.5-3 6.5-2.5 6.5.2 0 2-3.2 2.6-6.3 1.3" stroke="#0F5C4A" />
          <path d="M10 14.5 5.5 19" stroke="#0F5C4A" />
          <path d="M14 14.5 18.5 19" stroke="#0F5C4A" />
          <path d="M12 16.5V21" stroke="#F5A623" />
        </svg>
      );
    // High blood pressure: heart with amber pulse line
    case "heart-pulse":
    case "hypertension":
      return (
        <svg viewBox="0 0 24 24" className={className} {...baseProps}>
          <path
            d="M19.5 13.8c1.5-1.5 2.8-3.2 2.8-5.3A5.2 5.2 0 0 0 17 3.3c-1.8 0-3.1.8-4.5 2.2L12 6l-.5-.5C10.1 4.1 8.8 3.3 7 3.3A5.2 5.2 0 0 0 1.7 8.5c0 2.1 1.3 3.8 2.8 5.3L12 21l7.5-7.2Z"
            stroke="#0F5C4A"
          />
          <path d="M5 12h3.5l1.6-3.2 2.4 6.2 1.8-3H19" stroke="#F5A623" />
        </svg>
      );
    // Running stomach in children & ORS: cup with amber water drop
    case "droplet":
    case "child-diarrhoea-ors":
      return (
        <svg viewBox="0 0 24 24" className={className} {...baseProps}>
          <path d="M6.5 11.5h11l-1.3 8.2a2 2 0 0 1-2 1.8H9.8a2 2 0 0 1-2-1.8l-1.3-8.2Z" stroke="#0F5C4A" />
          <path d="M6.8 15.5h10.4" stroke="#0F5C4A" />
          <path
            d="M12 3s3.2 3.2 3.2 5.2a3.2 3.2 0 1 1-6.4 0C8.8 6.2 12 3 12 3Z"
            stroke="#F5A623"
          />
        </svg>
      );
    // Danger signs in pregnancy: calm two-colour pregnant silhouette
    case "baby":
    case "pregnancy-warning-signs":
      return (
        <svg viewBox="0 0 24 24" className={className} {...baseProps}>
          <circle cx="11.5" cy="5" r="2.2" stroke="#0F5C4A" />
          <path
            d="M10.5 8.5c-2 .5-3 2.5-3 5v6.5h4.2"
            stroke="#0F5C4A"
          />
          <path
            d="M13 8.5c2 .4 4.8 2.4 4.8 5.3 0 2.4-2 3.8-4.3 4.2v2"
            stroke="#F5A623"
          />
          <path d="M9.5 12.2c1.2.4 2.8.4 4 0" stroke="#0F5C4A" />
        </svg>
      );
    // Taking medicines safely: pill and clock
    case "pill":
    case "safe-medicine-use":
    default:
      return (
        <svg viewBox="0 0 24 24" className={className} {...baseProps}>
          <circle cx="15" cy="14.5" r="6" stroke="#0F5C4A" />
          <path d="M15 11.8v2.9l2 1.2" stroke="#F5A623" />
          <path
            d="M4.2 12.8 10 7a3.2 3.2 0 1 1 4.5 4.5l-1.8 1.8"
            stroke="#F5A623"
          />
          <path d="m7.1 9.9 2.9 2.9" stroke="#0F5C4A" />
        </svg>
      );
  }
};
