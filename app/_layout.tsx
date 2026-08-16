import React, { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ThemeProvider } from '@/components/panel/ui';
import { THEMES, ThemeName } from '@/constants/panelData';
import { PALETTE } from '@/constants/theme';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  useFonts,
} from '@expo-google-fonts/inter';
// Brand wordmark font — JetBrains Mono me capital I ke crossbars hote hain
// (Inter ka 'I' lowercase 'l' jaisa dikhta tha — user complaint).
import { JetBrainsMono_700Bold } from '@expo-google-fonts/jetbrains-mono';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient();

function RootLayoutNav() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: PALETTE.bg },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="index" />
      <Stack.Screen name="bootstrap" />
      <Stack.Screen name="main" />
      <Stack.Screen name="details" />
      <Stack.Screen name="settings" />
      <Stack.Screen name="switch" />
      <Stack.Screen name="broadcast" />
      <Stack.Screen name="tamper" />
      <Stack.Screen name="disclaimer" />
      <Stack.Screen name="drawer" options={{ presentation: 'transparentModal', animation: 'slide_from_left', contentStyle: { backgroundColor: 'transparent' } }} />
    </Stack>
  );
}

export default function RootLayout() {
  // Icon fonts bhi load karo — web pe ye automatic hote hain, par Android
  // simulator/device pe bina load kiye icons ke boxes dikhte hain.
  const [fontsLoaded, fontError] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    JetBrainsMono_700Bold,
    ...Feather.font,
    ...MaterialCommunityIcons.font,
  });

  useEffect(() => {
    if (fontsLoaded || fontError) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded, fontError]);

  const [theme, setTheme] = useState<ThemeName>('Ocean');
  const cycleTheme = () => setTheme((prev) => THEMES[(THEMES.indexOf(prev) + 1) % THEMES.length]);

  if (!fontsLoaded && !fontError) return null;

  return (
    <SafeAreaProvider>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <GestureHandlerRootView>
            <KeyboardProvider>
              <ThemeProvider value={{ theme, setTheme, cycleTheme }}>
                <StatusBar style="light" />
                <RootLayoutNav />
              </ThemeProvider>
            </KeyboardProvider>
          </GestureHandlerRootView>
        </QueryClientProvider>
      </ErrorBoundary>
    </SafeAreaProvider>
  );
}
