import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import DemoGate from './components/DemoGate';
import './index.css';
import { ensureServiceWorker } from './notificationHelper';

// Register + activate the SW early so it's ready when notifications fire.
// ensureServiceWorker() handles secure-context checks internally.
ensureServiceWorker();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <DemoGate>
      <AuthProvider>
        <App />
      </AuthProvider>
    </DemoGate>
  </React.StrictMode>
);