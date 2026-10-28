import React, { useState, useEffect, useRef } from 'react';
import { Card, Space, Typography, message, Spin } from 'antd';
import { authAPI } from '../services/api';

const { Title, Text } = Typography;

// Google Client ID from environment
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

// Declare Google types
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select: boolean;
            cancel_on_tap_outside: boolean;
          }) => void;
          renderButton: (element: HTMLElement, config: {
            theme: string;
            size: string;
            width: number;
            text: string;
          }) => void;
          prompt: () => void;
        };
      };
    };
  }
}

interface LoginPageProps {
  onLogin: (token: string) => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [loading, setLoading] = useState(false);
  const [, setGoogleReady] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement>(null);

  // Handle Google callback
  const handleGoogleCallback = async (response: { credential: string }) => {
    setLoading(true);
    try {
      const authResponse = await authAPI.googleLogin(response.credential);
      onLogin(authResponse.access_token);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Google login failed');
    } finally {
      setLoading(false);
    }
  };

  // Initialize Google Sign-In
  useEffect(() => {
    const initializeGoogleSignIn = () => {
      if (!window.google?.accounts?.id) {
        // Google script not loaded yet, retry
        setTimeout(initializeGoogleSignIn, 100);
        return;
      }

      if (!GOOGLE_CLIENT_ID) {
        console.error('VITE_GOOGLE_CLIENT_ID is not configured');
        return;
      }

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleCallback,
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      // Render Google button
      if (googleButtonRef.current) {
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'signin_with',
        });
        setGoogleReady(true);
      }
    };

    initializeGoogleSignIn();
  }, []);

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card
        style={{
          width: 420,
          borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
          padding: '24px',
        }}
      >
        <Space
          direction="vertical"
          size="large"
          style={{ width: '100%', textAlign: 'center' }}
        >
          {/* Logo */}
          <div style={{ marginBottom: 8 }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="#1890ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="#1890ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="#1890ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>

          <Title level={2} style={{ marginBottom: 0, letterSpacing: 2 }}>
            BLADE Admin
          </Title>
          <Text type="secondary">
            Admin Portal - Authorized Personnel Only
          </Text>

          {/* Google Sign-In Button */}
          <Spin spinning={loading}>
            <div
              ref={googleButtonRef}
              style={{
                display: 'flex',
                justifyContent: 'center',
                minHeight: 44,
                marginTop: 16,
              }}
            />
          </Spin>

          {!GOOGLE_CLIENT_ID && (
            <Text type="danger" style={{ fontSize: 12 }}>
              Google Client ID not configured
            </Text>
          )}

          <Text type="secondary" style={{ fontSize: 12, marginTop: 16 }}>
            Only administrators can access this portal
          </Text>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
