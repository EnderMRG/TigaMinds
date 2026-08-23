"use client";

import { useLanguage } from '@/context/LanguageContext';
import { Button } from '@/components/ui/button';
import { Languages } from 'lucide-react';

export function LanguageToggle() {
    const { language, toggleLanguage } = useLanguage();

    return (
        <Button
            onClick={toggleLanguage}
            variant="outline"
            size="sm"
            className="gap-2 font-medium"
            title={language === 'en' ? 'Switch to Assamese' : 'Switch to English'}
        >
            <Languages className="h-4 w-4" />
            <span className="hidden sm:inline">
                {language === 'en' ? 'অসমীয়া' : 'English'}
            </span>
            <span className="sm:hidden">
                {language === 'en' ? 'AS' : 'EN'}
            </span>
        </Button>
    );
}
