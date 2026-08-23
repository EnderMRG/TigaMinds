/**
 * API Client for ChaiTea Backend
 * Automatically injects Firebase ID token in Authorization header
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiClient {
    private getToken: (() => Promise<string | null>) | null = null;
    private getExtraHeaders: (() => Record<string, string>) | null = null;

    setTokenGetter(getter: () => Promise<string | null>) {
        this.getToken = getter;
    }

    setHeaderInjector(injector: () => Record<string, string>) {
        this.getExtraHeaders = injector;
    }

    private async getHeaders(): Promise<HeadersInit> {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };

        if (this.getToken) {
            const token = await this.getToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            } else {
                console.warn('⚠️ No auth token available');
            }
        }

        if (this.getExtraHeaders) {
            const extra = this.getExtraHeaders();
            Object.assign(headers, extra);
        }

        return headers;
    }

    async get(endpoint: string) {
        const headers = await this.getHeaders();
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'GET',
            headers,
        });

        if (!response.ok) {
            console.error('❌ API Error:', response.status, response.statusText);
            throw new Error(`API Error: ${response.statusText}`);
        }

        return response.json();
    }

    async post(endpoint: string, data?: any) {
        const headers = await this.getHeaders();
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers,
            body: data ? JSON.stringify(data) : undefined,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }

        return response.json();
    }

    async postFormData(endpoint: string, formData: FormData) {
        const token = this.getToken ? await this.getToken() : null;
        const headers: Record<string, string> = {};

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        if (this.getExtraHeaders) {
            const extra = this.getExtraHeaders();
            Object.assign(headers, extra);
        }

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }

        return response.json();
    }
}

export const apiClient = new ApiClient();
