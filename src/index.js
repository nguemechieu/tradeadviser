import React, {StrictMode} from 'react';

import './index.css';
import App from './App';
import { AuthProvider } from './context/AuthProvider';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import {createRoot} from "react-dom/client";

    createRoot(
        document.getElementById('root')
    ).render(
        <StrictMode>
            <BrowserRouter>
                <AuthProvider>
                    <Routes>
                        <Route path="/*" element={<App/>}/>
                    </Routes>
                </AuthProvider>
            </BrowserRouter>
        </StrictMode>
    );
