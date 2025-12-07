import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ThemeProvider } from './context/ThemeContext'
import Navbar from './components/Navbar'
import DustEffect from './components/DustEffect'
import RoadmapView from './pages/RoadmapView'
import Home from './pages/Home'
import Import from './pages/Import'
import Edit from './pages/Edit'
import Login from './pages/Login'
import { SignedIn, SignedOut } from "@clerk/clerk-react"
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
                    {/* Protected Routes */}
                    <Route path="/" element={<Home />} />
                    <Route path="/import" element={<Import />} />
                    <Route path="/roadmap/:id" element={<RoadmapView />} />
                    <Route path="/edit/:id" element={<Edit />} />
                </Routes>
            </motion.div>
        </AnimatePresence>
    )
}

function App() {
    return (
        <Router>
            <ThemeProvider>
                <Routes>
                    {/* Public Route: Login */}
                    <Route path="/login" element={<Login />} />

                    {/* All other routes are protected */}
                    <Route path="*" element={
                        <>
                            <SignedIn>
                                <div className="app-container">
                                    <DustEffect />
                                    <h1 className="app-title">TRAQO</h1>
                                    <Navbar />
                                    <div className="content-container">
                                        <AnimatedRoutes />
                                    </div>
                                </div>
                            </SignedIn>
                            <SignedOut>
                                <Navigate to="/login" replace />
                            </SignedOut>
                        </>
                    } />
                </Routes>
            </ThemeProvider>
        </Router>
    )
}

export default App
