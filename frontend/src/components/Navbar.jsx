import { Link, useLocation } from 'react-router-dom'
import { Plus, Library } from 'lucide-react'
import TraqoLogo from './TraqoLogo'

export default function Navbar() {
    const location = useLocation()
    const links = [
        { path: '/', label: 'Library', icon: Library },
        { path: '/import', label: 'New', icon: Plus },
    ]

    return (
        <header className="navbar-custom">
            <div className="navbar-inner">
                <Link to="/" className="brand-lockup" aria-label="Traqo home">
                    <TraqoLogo className="brand-mark" />
                    <span className="brand-wordmark">
                        <strong>Traqo</strong>
                        <small>Document workspace</small>
                    </span>
                </Link>

                <nav className="nav-links" aria-label="Primary navigation">
                    {links.map((link) => {
                        const isLibraryRoute = link.path === '/' && (
                            location.pathname === '/' ||
                            location.pathname.startsWith('/roadmap/') ||
                            location.pathname.startsWith('/edit/')
                        )
                        const isActive = isLibraryRoute || location.pathname === link.path
                        return (
                            <Link
                                to={link.path}
                                key={link.path}
                                className={`nav-link-container ${isActive ? 'active' : ''}`}
                                aria-current={isActive ? 'page' : undefined}
                            >
                                <link.icon size={15} aria-hidden="true" />
                                <span>{link.label}</span>
                            </Link>
                        )
                    })}
                </nav>

                <span className="local-status"><i aria-hidden="true" /> Local</span>
            </div>
        </header>
    )
}
