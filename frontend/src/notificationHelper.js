/* ─────────────────────────────────────────────────────────────
   notificationHelper.js
   Cross-platform notification utility for Expediramp.

   Problem:
     macOS Chrome & Safari handle web notifications differently
     from Windows/Linux. Specifically:
       1. macOS Chrome: `registration.showNotification()` called
          from the PAGE context sometimes silently fails. The
          notification must come from the SERVICE WORKER context.
       2. macOS Safari: Does not support the `new Notification()`
          constructor at all in recent versions; it requires
          notifications to go through a service worker's
          `showNotification()`, and even that only works if the
          SW is properly activated and controlling the page.
       3. Both: The `renotify` option can cause silent failures
          if not paired with a `tag`, or if unsupported.

   Fix:
     - Primary path: postMessage to the SW, which calls
       `self.registration.showNotification()` inside the SW
       context. This is the most reliable cross-platform path.
     - Fallback 1: `registration.showNotification()` from page
       (works on Windows/Linux Chrome, sometimes macOS Chrome).
     - Fallback 2: `new Notification()` constructor (works on
       older Chrome on all platforms, never on Safari).
   ───────────────────────────────────────────────────────────── */

/**
 * Detect if we're on macOS.
 */
function isMacOS() {
  if (typeof navigator === 'undefined') return false;
  // navigator.userAgentData is the modern approach
  if (navigator.userAgentData?.platform) {
    return navigator.userAgentData.platform === 'macOS';
  }
  // Fallback to userAgent string
  return /Mac/i.test(navigator.userAgent);
}

/**
 * Get an active, controlling service worker registration.
 * Times out after `ms` to avoid hanging on browsers where
 * `navigator.serviceWorker.ready` never resolves.
 */
async function getSwRegistration(ms = 3000) {
  if (!('serviceWorker' in navigator)) return null;

  try {
    const registration = await Promise.race([
      navigator.serviceWorker.ready,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('SW ready timeout')), ms)
      ),
    ]);
    return registration || null;
  } catch {
    return null;
  }
}

/**
 * Try to show a notification by posting a message to the SW.
 * This is the most reliable path on macOS.
 */
async function notifyViaSWMessage(title, body) {
  const registration = await getSwRegistration();
  if (!registration?.active) return false;

  try {
    registration.active.postMessage({
      type: 'SHOW_NOTIFICATION',
      title,
      body,
    });
    // We can't know for sure the SW handled it, but if the SW
    // is active this is the most reliable path on macOS.
    return true;
  } catch (err) {
    console.warn('[notify] SW postMessage failed:', err);
    return false;
  }
}

/**
 * Try to show a notification via registration.showNotification()
 * called from the page context (not the SW).
 */
async function notifyViaRegistration(title, body) {
  const registration = await getSwRegistration();
  if (!registration?.showNotification) return false;

  try {
    await registration.showNotification(title, {
      body,
      tag: 'expediramp-request-finished',
      renotify: true,
    });
    return true;
  } catch (err) {
    console.warn('[notify] registration.showNotification failed:', err);
    // Retry without renotify — some browsers choke on it
    try {
      await registration.showNotification(title, {
        body,
        tag: 'expediramp-request-finished',
      });
      return true;
    } catch (err2) {
      console.warn('[notify] registration.showNotification (no renotify) failed:', err2);
      return false;
    }
  }
}

/**
 * Try the Notification constructor (oldest fallback).
 * Does NOT work on Safari at all.
 */
function notifyViaConstructor(title, body) {
  try {
    // eslint-disable-next-line no-new
    new Notification(title, {
      body,
      tag: 'expediramp-request-finished',
    });
    return true;
  } catch (err) {
    console.warn('[notify] Notification constructor failed:', err);
    return false;
  }
}

/**
 * Show a notification using the best available method for the
 * current platform. Tries multiple strategies in order.
 *
 * @param {string} title
 * @param {string} body
 * @returns {Promise<boolean>} whether a notification was fired
 */
export async function showNotification(title, body) {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return false;
  }
  if (Notification.permission !== 'granted') {
    return false;
  }

  const mac = isMacOS();

  // On macOS, strongly prefer the SW message path
  if (mac) {
    if (await notifyViaSWMessage(title, body)) return true;
    if (await notifyViaRegistration(title, body)) return true;
    // Constructor almost never works on modern macOS Safari,
    // but try it as a last resort
    return notifyViaConstructor(title, body);
  }

  // On Windows / Linux: the original approach works fine,
  // but we still try the most reliable path first.
  if (await notifyViaSWMessage(title, body)) return true;
  if (await notifyViaRegistration(title, body)) return true;
  return notifyViaConstructor(title, body);
}

/**
 * Request notification permission. Must be called from a user
 * gesture (click handler) to work on all browsers.
 *
 * @returns {Promise<'granted'|'denied'|'default'>}
 */
export async function requestPermission() {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'denied';
  }

  if (Notification.permission === 'granted') {
    return 'granted';
  }

  try {
    const result = await Notification.requestPermission();
    return result;
  } catch {
    // Older callback-based API
    return new Promise((resolve) => {
      Notification.requestPermission((perm) => resolve(perm));
    });
  }
}

/**
 * Ensure the service worker is registered and activated.
 * Call this early (e.g. on app mount) so that by the time a
 * notification needs to fire, the SW is ready.
 */
export async function ensureServiceWorker() {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;

  try {
    const registration = await navigator.serviceWorker.register('/sw.js');

    // If there's a waiting worker, activate it immediately
    if (registration.waiting) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }

    // Listen for new workers and auto-activate
    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      if (!newWorker) return;
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'activated') {
          // SW is now active and controlling
        }
      });
    });
  } catch (err) {
    console.error('[notify] SW registration failed:', err);
  }
}
