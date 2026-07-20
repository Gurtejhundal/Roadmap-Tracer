import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Map, Plus, Library } from 'lucide-react'

export default function Navbar() {
    const location = useLocation()
    const links = [
        { path: '/', label: 'Library', icon: Library },
        { path: '/import', label: 'New roadmap', icon: Plus },
    ]

    return (
        <nav className="navbar-custom">
            <Link to="/" className="brand-lockup" aria-label="Traqo home">
                <img 
                  src="/android-chrome-192x192.png" 
                  alt="Traqo Logo" 
                  className="brand-mark" 
                  style={{ background: "transparent", boxShadow: "none", transform: "none", borderRadius: "0" }}
                />
                <span><strong>Traqo</strong><small>Roadmap workspace</small></span>
            </Link>

            {/* Center: Navigation Links */}
            <div className="nav-center">
                <div className="nav-links">
                    {links.map((link) => {
                        const isLibraryRoute = link.path === '/' && (
                            location.pathname === '/' ||
                            location.pathname.startsWith('/roadmap/') ||
                            location.pathname.startsWith('/edit/')
                        )
                        const isActive = isLibraryRoute || location.pathname === link.path
                        return (
                            <Link to={link.path} key={link.path} className="nav-link-container">
                                <link.icon size={16} aria-hidden="true" />
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

            <span className="local-status"><i /> Local workspace</span>

        </nav>
    )
}
