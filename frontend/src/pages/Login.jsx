import React from 'react';
import { SignIn } from "@clerk/clerk-react";
import { motion } from 'framer-motion';
import DustEffect from '../components/DustEffect';

export default function Login() {
    return (
        <div className="login-page">
            <DustEffect />

            {/* Minimalist Blue & Pink Glows - High Opacity */}
            <motion.div
                animate={{ opacity: [0.3, 0.6, 0.3], scale: [1, 1.1, 1] }}
                transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
                className="elemental-glow glow-blue"
            />
            <motion.div
                animate={{ opacity: [0.3, 0.6, 0.3], scale: [1, 1.2, 1] }}
                transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 2 }}
                className="elemental-glow glow-pink"
            />

            <div className="content-wrapper">
                <motion.div
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8 }}
                    className="brand-header"
                >
                    <h1 className="brand-title">TRAQO</h1>
                    <p className="brand-subtitle">Your roadmap won’t fix your laziness. You will.</p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="login-card"
                >
                    <SignIn
                        appearance={{
                            layout: {
                                socialButtonsPlacement: 'bottom',
                                socialButtonsVariant: 'iconButton',
                                logoPlacement: 'none'
                            },
                            variables: {
                                colorPrimary: '#f8fafc',
                                colorText: '#ffffff',
                                colorBackground: 'transparent',
                                colorInputBackground: 'rgba(0,0,0,0.3)',
                                colorInputText: '#fff',
                                colorTextSecondary: '#94a3b8',
                                fontFamily: '"Outfit", sans-serif',
                                borderRadius: '12px',
                            },
                            elements: {
                                headerTitle: { display: 'none' },
                                headerSubtitle: { display: 'none' },
                                rootBox: { width: '100%', boxSizing: 'border-box' },
                                cardBox: { width: '100%', boxSizing: 'border-box' },
                                card: {
                                    backgroundColor: 'transparent',
                                    boxShadow: 'none',
                                    padding: '0',
                                    border: 'none',
                                    fontSize: '0.95rem',
                                    borderRadius: '12px',
                                    transition: 'all 0.2s',
                                    boxSizing: 'border-box',
                                    width: '100%'
                                },

                                // Social Buttons: White Tiles with Black Icons
                                socialButtonsIconButton: {
                                    backgroundColor: 'white',
                                    color: 'black',
                                    height: '44px',
                                    borderRadius: '12px',
                                    border: 'none',
                                    transition: 'all 0.2s ease',
                                    '&:hover': {
                                        backgroundColor: '#f1f5f9',
                                        transform: 'translateY(-2px)'
                                    }
                                },

                                // Inputs: Clean & Dark
                                formFieldInput: {
                                    backgroundColor: 'rgba(0,0,0,0.4)',
                                    border: '1px solid rgba(255, 255, 255, 0.1)',
                                    padding: '14px',
                                    fontSize: '0.95rem',
                                    borderRadius: '12px',
                                    transition: 'all 0.2s',
                                    boxSizing: 'border-box',
                                    '&:focus': {
                                        borderColor: '#ec4899', // Pink Focus
                                        boxShadow: '0 0 0 1px rgba(236, 72, 153, 0.3)'
                                    }
                                },
                                formFieldLabel: {
                                    color: '#64748b',
                                    fontSize: '0.85rem',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    marginBottom: '6px'
                                },

                                // Primary Button: Minimalist White
                                formButtonPrimary: {
                                    background: 'white',
                                    color: 'black',
                                    border: 'none',
                                    marginTop: '1.5rem',
                                    width: '100%',
                                    padding: '14px',
                                    fontSize: '1rem',
                                    fontWeight: '600',
                                    transition: 'all 0.2s',
                                    borderRadius: '12px',
                                    '&:hover': {
                                        background: '#e2e8f0',
                                        transform: 'translateY(-1px)'
                                    }
                                },
                                footerActionLink: { color: '#94a3b8', textDecoration: 'underline' },
                                dividerLine: { background: 'rgba(255,255,255,0.1)' },
                                dividerText: { color: '#475569' }
                            }
                        }}
                    />
                </motion.div>
            </div>

            <style>{`
        .login-page {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #000; /* True Black */
            overflow: hidden;
            font-family: 'Outfit', sans-serif;
            z-index: 10000;
            color: white;
        }

        /* Elemental Glows */
        .elemental-glow {
            position: absolute;
            border-radius: 50%;
            filter: blur(120px);
            z-index: 1;
        }
        .glow-blue {
            width: 50vw;
            height: 50vw;
            background: radial-gradient(circle, #3b82f6, transparent 60%); /* Blue */
            top: -20%;
            left: -10%;
            opacity: 0.3;
        }
        .glow-pink {
            width: 50vw;
            height: 50vw;
            background: radial-gradient(circle, #ec4899, transparent 60%); /* Pink */
            bottom: -20%;
            right: -10%;
            opacity: 0.3;
        }

        .content-wrapper {
            position: relative;
            z-index: 10;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
            padding: 1rem;
            box-sizing: border-box;
        }

        .brand-header {
            text-align: center;
            margin-bottom: 2rem;
        }

        .brand-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 3rem;
            font-weight: 700;
            margin: 0;
            color: white;
            letter-spacing: -0.03em;
        }

        .brand-subtitle {
            color: #64748b;
            font-size: 1rem;
            margin-top: 0.5rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        .login-card {
            background: rgba(10, 10, 10, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 3rem; 
            width: 100%;
            max-width: 450px; 
            box-sizing: border-box;
            box-shadow: 0 0 40px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        /* Force children to fill width */
        .cl-rootBox, .cl-cardBox, .cl-element {
            width: 100% !important;
            box-sizing: border-box !important;
        }

        @media (max-width: 500px) {
            .login-card {
                padding: 2rem;
                border: none;
                background: transparent;
            }
            .brand-title { font-size: 2.5rem; }
        }
      `}</style>
        </div>
    );
}
