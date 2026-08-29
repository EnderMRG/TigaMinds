// @ts-nocheck
self.addEventListener('push', (event) => {
  let data = {
    title: "TigaMinds Alert",
    body: "You have a new notification.",
    url: "/"
  };
  
  try {
    if (event.data) {
      // Data can be text or JSON. If it's a simple text:
      try {
        const jsonData = event.data.json();
        data = { ...data, ...jsonData };
      } catch (e) {
        data.body = event.data.text();
      }
    }
  } catch (e) {
    console.error("Failed to parse push data", e);
  }
  
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icon-192x192.png',
      badge: '/icon-192x192.png',
      vibrate: [100, 50, 100],
      data: { url: data.url }
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clientsArr) => {
      const url = event.notification.data.url || '/';
      const hadWindowToFocus = clientsArr.some((windowClient) => {
        if (windowClient.url === url || windowClient.url.includes(url)) {
          windowClient.focus();
          return true;
        }
        return false;
      });
      if (!hadWindowToFocus && self.clients.openWindow) {
        self.clients.openWindow(url);
      }
    })
  );
});
