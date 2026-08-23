'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Bell, Send, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

export default function WorkerAlerts() {
  const [phone, setPhone] = useState('');
  const [message, setMessage] = useState('');
  const [bulkPhones, setBulkPhones] = useState('');
  const [isSingleMode, setIsSingleMode] = useState(true);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [statusMessage, setStatusMessage] = useState('');

  const sendSingleAlert = async () => {
    if (!phone.trim() || !message.trim()) {
      setStatus('error');
      setStatusMessage('Please enter phone number and message');
      return;
    }

    setLoading(true);
    setStatus('idle');

    try {
      const response = await apiClient.post('/send-sms', {
        phone: phone.trim(),
        message: message.trim(),
      });

      if (response.success) {
        setStatus('success');
        setStatusMessage(`Alert sent successfully! Message ID: ${response.message_sid}`);
        setPhone('');
        setMessage('');
      } else {
        setStatus('error');
        setStatusMessage(response.error || 'Failed to send alert');
      }
    } catch (error: any) {
      setStatus('error');
      setStatusMessage(error.message || 'Error sending alert');
    } finally {
      setLoading(false);
    }
  };

  const sendBulkAlerts = async () => {
    const phones = bulkPhones
      .split('\n')
      .map((p) => p.trim())
      .filter((p) => p.length > 0);

    if (phones.length === 0 || !message.trim()) {
      setStatus('error');
      setStatusMessage('Please enter phone numbers and message');
      return;
    }

    setLoading(true);
    setStatus('idle');

    try {
      const response = await apiClient.post('/send-bulk-sms', {
        phones,
        message: message.trim(),
      });

      if (response.success) {
        setStatus('success');
        setStatusMessage(
          `Alerts sent: ${response.sent} successful, ${response.failed} failed`
        );
        setBulkPhones('');
        setMessage('');
      } else {
        setStatus('error');
        setStatusMessage(response.error || 'Failed to send alerts');
      }
    } catch (error: any) {
      setStatus('error');
      setStatusMessage(error.message || 'Error sending alerts');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-6">
        <Bell className="h-6 w-6 text-primary" />
        <h2 className="text-2xl font-bold text-foreground">Worker Alerts</h2>
      </div>

      {/* Mode Toggle */}
      <div className="flex gap-4">
        <Button
          variant={isSingleMode ? 'default' : 'outline'}
          onClick={() => setIsSingleMode(true)}
          className="flex-1"
        >
          Single Alert
        </Button>
        <Button
          variant={!isSingleMode ? 'default' : 'outline'}
          onClick={() => setIsSingleMode(false)}
          className="flex-1"
        >
          Bulk Alert
        </Button>
      </div>

      {/* Alert Form */}
      <Card className="p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            {isSingleMode ? 'Worker Phone Number' : 'Phone Numbers (one per line)'}
          </label>
          {isSingleMode ? (
            <Input
              type="tel"
              placeholder="+91XXXXXXXXXX"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={loading}
              className="bg-background"
            />
          ) : (
            <Textarea
              placeholder="+91XXXXXXXXXX&#10;+91YYYYYYYYYY&#10;+91ZZZZZZZZZZ"
              value={bulkPhones}
              onChange={(e) => setBulkPhones(e.target.value)}
              disabled={loading}
              className="bg-background font-mono"
              rows={5}
            />
          )}
          <p className="text-xs text-muted-foreground mt-2">
            Use E.164 format: +[country_code][phone_number]
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Alert Message
          </label>
          <Textarea
            placeholder="Enter alert message (supports regional languages)..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={loading}
            className="bg-background"
            rows={4}
          />
          <p className="text-xs text-muted-foreground mt-2">
            Character count: {message.length}
          </p>
        </div>

        {/* Status Messages */}
        {status === 'success' && (
          <div className="flex items-start gap-3 p-4 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg">
            <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-green-700 dark:text-green-300">{statusMessage}</p>
          </div>
        )}

        {status === 'error' && (
          <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg">
            <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-700 dark:text-red-300">{statusMessage}</p>
          </div>
        )}

        {/* Send Button */}
        <Button
          onClick={isSingleMode ? sendSingleAlert : sendBulkAlerts}
          disabled={loading}
          className="w-full bg-primary hover:bg-primary/90"
          size="lg"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Sending...
            </>
          ) : (
            <>
              <Send className="h-4 w-4 mr-2" />
              Send Alert
            </>
          )}
        </Button>
      </Card>

      {/* Info Card */}
      <Card className="p-4 bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
        <p className="text-sm text-blue-900 dark:text-blue-200">
          <strong>💡 Tip:</strong> Use this feature to send real-time alerts to your workers about
          tasks, weather conditions, or urgent instructions. Messages support regional languages
          like Bengali (বাংলা), Hindi (हिन्दी), and more!
        </p>
      </Card>
    </div>
  );
}
