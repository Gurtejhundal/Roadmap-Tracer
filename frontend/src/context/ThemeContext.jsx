import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};

export const ThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        const savedTheme = localStorage.getItem('app-theme');
        return savedTheme || 'water';
    });

    useEffect(() => {
        const root = document.body;
        // Remove existing theme classes
        root.classList.remove('theme-default', 'theme-water', 'theme-fire', 'theme-earth', 'theme-air');
        // Add new theme class
        root.classList.add(`theme-${theme}`);
        // Save to local storage
        localStorage.setItem('app-theme', theme);
    }, [theme]);

    return (
        <ThemeContext.Provider value={{ theme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};
