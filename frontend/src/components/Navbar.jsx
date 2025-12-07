import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Droplets, Flame, Mountain, Wind } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { UserButton } from '@clerk/clerk-react'

export default function Navbar() {
    const location = useLocation()
    const { theme, setTheme } = useTheme()

    const links = [
        { path: '/import', label: 'Import Roadmap' },
        { path: '/', label: 'View Tasks' },
    ]

    return (
        <nav className="navbar-custom">
            {/* Left: User Profile */}
            <div className="nav-left">
                <img src="/logo.jpg" alt="TRAQO Logo" className="navbar-logo" style={{ height: '32px', marginRight: '1rem', borderRadius: '50%' }} />
                <div className="profile-wrapper">
                    <UserButton afterSignOutUrl="/login" />
                    <span className="profile-label">Profile</span>
                </div>
            </div>

            {/* Center: Navigation Links */}
            <div className="nav-center">
                <div className="nav-links">
                    {links.map((link) => {
                        const isActive = location.pathname === link.path
                        return (
                            <Link to={link.path} key={link.path} className="nav-link-container">
                                <span className={`nav-link ${isActive ? 'active' : ''}`}>
                                    {link.label}
                                </span>
                                {isActive && (
                                    <motion.div
                                        layoutId="nav-indicator"
                                        className="nav-indicator"
                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                    />
                                )}
                            </Link>
                        )
                    })}
                </div>
            </div>

            {/* Right: Theme Switcher (Direct Selection) */}
            <div className="nav-right">
                <div className="theme-switcher-row">
                    <button
                        onClick={() => setTheme('water')}
                        className={`theme-icon-btn ${theme === 'water' ? 'active' : ''}`}
                        title="Water Theme"
                    >
                        <Droplets size={18} />
                    </button>
                    <button
                        onClick={() => setTheme('fire')}
                        className={`theme-icon-btn ${theme === 'fire' ? 'active' : ''}`}
                        title="Fire Theme"
                    >
                        <Flame size={18} />
                    </button>
                    <button
                        onClick={() => setTheme('earth')}
                        className={`theme-icon-btn ${theme === 'earth' ? 'active' : ''}`}
                        title="Earth Theme"
                    >
                        <Mountain size={18} />
                    </button>
                    <button
                        onClick={() => setTheme('air')}
                        className={`theme-icon-btn ${theme === 'air' ? 'active' : ''}`}
                        title="Air Theme"
                    >
                        <Wind size={18} />
                    </button>
                </div>
            </div>

            <style>{`
                .navbar-custom {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1.5rem 2rem;
                    margin-bottom: 2rem;
                    width: 100%;
                    box-sizing: border-box;
                    background: transparent;
                    position: relative;
                    z-index: 100;
                }

                .nav-left, .nav-right {
                    flex: 1;
                    display: flex;
                    align-items: center;
                }

                .nav-left {
                    justify-content: flex-start;
                }

                .nav-right {
                    justify-content: flex-end;
                }

                .nav-center {
                    flex: 2;
                    display: flex;
                    justify-content: center;
                }

                .profile-wrapper {
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    background: rgba(255, 255, 255, 0.05);
                    padding: 6px 16px 6px 6px;
                    border-radius: 50px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    transition: all 0.3s ease;
                }

                .profile-wrapper:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-color: rgba(255, 255, 255, 0.2);
                }

                .profile-label {
                    font-size: 0.9rem;
                    font-weight: 500;
                    color: var(--muted);
                }

                .theme-switcher-row {
                    display: flex;
                    gap: 0.5rem;
                    background: rgba(255, 255, 255, 0.05);
                    padding: 6px;
                    border-radius: 50px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }

                .theme-icon-btn {
                    background: transparent;
                    border: none;
                    color: var(--muted);
                    padding: 8px;
                    border-radius: 50%;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.2s ease;
                }

                .theme-icon-btn:hover {
                    color: white;
                    background: rgba(255, 255, 255, 0.1);
                }

                .theme-icon-btn.active {
                    background: var(--primary);
                    color: white;
                    box-shadow: 0 0 10px var(--primary);
                }

                /* Mobile Responsive */
                @media (max-width: 768px) {
                    .navbar-custom {
                        flex-direction: column;
                        gap: 1rem;
                        padding: 1rem;
                    }
                    .nav-left, .nav-right, .nav-center {
                        justify-content: center;
                        width: 100%;
                    }
                }
            `}</style>
        </nav>
    )
}
