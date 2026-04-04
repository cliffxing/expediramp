/* ─────────────────────────────────────────────────────────────
   Expediramp Service Worker
   Handles notification display + click for all platforms,
   including macOS Chrome and Safari.
   ───────────────────────────────────────────────────────────── */

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

/* ── Message-based notification trigger ──────────────────────
   The main thread sends { type: 'SHOW_NOTIFICATION', title, body }
   so we can display a notification from the SW context.
   This works more reliably on macOS Chrome than calling
   registration.showNotification() from the page itself,
   because the SW is a persistent context that macOS treats
   as a proper notification source.
   ──────────────────────────────────────────────────────────── */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    const { title, body } = event.data;
    event.waitUntil(
      self.registration.showNotification(title, {
        body: body || '',
        tag: 'expediramp-request-finished',
        renotify: true,
        // icon could be added here if you have one:
        // icon: '/icon-192.png',
      }).catch((err) => {
        console.warn('[SW] showNotification via message failed:', err);
      })
    );
  }
});

/* ── Push event (future-proofing for Safari Web Push) ─────── */
self.addEventListener('push', (event) => {
  let title = 'Expediramp';
  let body = 'Your request is ready.';

  if (event.data) {
    try {
      const data = event.data.json();
      title = data.title || title;
      body = data.body || body;
    } catch {
      body = event.data.text() || body;
    }
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: 'expediramp-request-finished',
      renotify: true,
    })
  );
});

/* ── Notification click → focus or open the app ─────────── */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil((async () => {
    const allClients = await self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true,
    });

    for (const client of allClients) {
      if ('focus' in client) {
        await client.focus();
        return;
      }
    }

    if (self.clients.openWindow) {
      await self.clients.openWindow('/');
    }
  })());
});