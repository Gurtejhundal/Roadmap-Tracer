import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ThemeProvider } from './context/ThemeContext'
import Navbar from './components/Navbar'
import DustEffect from './components/DustEffect'
import RoadmapView from './pages/RoadmapView'
import Home from './pages/Home'
import Import from './pages/Import'
import Edit from './pages/Edit'
import './index.css'

function AnimatedRoutes() {
    const location = useLocation()

    return (
        <AnimatePresence mode="wait">
            <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="page-content"
            >
                <Routes location={location} key={location.pathname}>
                    <Route path="/" element={<Home />} />
                    <Route path="/import" element={<Import />} />
                    <Route path="/roadmap/:id" element={<RoadmapView />} />
                    <Route path="/edit/:id" element={<Edit />} />
                    <Route path="*" element={<Home />} />
                </Routes>
            </motion.div>
        </AnimatePresence>
    )
}

function App() {
    return (
        <Router>
            <ThemeProvider>
                <div className="app-container">
                    <DustEffect />
                    <h1 className="app-title">TRAQO</h1>
                    <Navbar />
                    <div className="content-container">
                        <AnimatedRoutes />
                    </div>
                </div>
            </ThemeProvider>
        </Router>
    )
}

export default App
