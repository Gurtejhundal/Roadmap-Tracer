import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import RoadmapView from './pages/RoadmapView'
import Home from './pages/Home'
import Import from './pages/Import'
import Edit from './pages/Edit'
import './index.css'

function AppRoutes() {
    return (
        <div className="page-content">
            <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/import" element={<Import />} />
                <Route path="/roadmap/:id" element={<RoadmapView />} />
                <Route path="/edit/:id" element={<Edit />} />
                <Route path="*" element={<Home />} />
            </Routes>
        </div>
    )
}

function App() {
    return (
        <Router>
            <div className="app-container">
                <Navbar />
                <div className="content-container">
                    <AppRoutes />
                </div>
            </div>
        </Router>
    )
}

export default App
