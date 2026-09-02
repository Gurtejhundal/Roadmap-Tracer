export default function TraqoLogo({ className = '' }) {
    return (
        <svg
            className={className}
            viewBox="0 0 28 28"
            aria-hidden="true"
            focusable="false"
        >
            <rect
                x="1.25"
                y="1.25"
                width="25.5"
                height="25.5"
                rx="5.25"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
            />
            <path
                d="M7.75 8.5h12.5M14 8.5v10.25"
                fill="none"
                stroke="currentColor"
                strokeLinecap="square"
                strokeWidth="2.25"
            />
            <circle cx="20" cy="19.25" r="1.75" fill="currentColor" />
        </svg>
    )
}
