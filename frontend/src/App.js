import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { Toaster } from "./components/ui/sonner";
import DocumentProcessor from "./components/DocumentProcessor";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const savedMode = localStorage.getItem('darkMode');
    if (savedMode) {
      setDarkMode(JSON.parse(savedMode));
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <div className={`min-h-screen transition-colors duration-300 ${
      darkMode ? 'dark bg-zinc-950 text-white' : 'bg-gray-50 text-zinc-900'
    }`}>
      <BrowserRouter>
        <div className="min-h-screen">
          <Routes>
            <Route 
              path="/" 
              element={
                <DocumentProcessor 
                  darkMode={darkMode} 
                  setDarkMode={setDarkMode} 
                  apiEndpoint={API}
                />
              } 
            />
          </Routes>
        </div>
      </BrowserRouter>
      <Toaster 
        position="bottom-right" 
        richColors 
        theme={darkMode ? 'dark' : 'light'}
      />
    </div>
  );
}

export default App;