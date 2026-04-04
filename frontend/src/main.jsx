import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import DemoGate from './components/DemoGate';
import './index.css';

if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) => {
      console.error('Failed to register service worker for notifications:', error);
    });
  });
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <DemoGate>
      <AuthProvider>
        <App />
      </AuthProvider>
    </DemoGate>
  </React.StrictMode>
);
