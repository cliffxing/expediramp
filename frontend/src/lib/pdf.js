function formatDate(dateStr, options = { month: 'short', day: 'numeric', year: 'numeric' }) {
  if (!dateStr) return 'TBD';
  try {
    const date = new Date(`${dateStr}T12:00:00`);
    if (Number.isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('en-US', options);
  } catch {
    return dateStr;
  }
}

function formatCurrency(amount, item = {}) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return null;
  const symbol = item.currency_symbol || item.details?.currency_symbol || '$';
  const code = item.currency_code || item.details?.currency_code || 'USD';
  const value = Number(amount).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return code === 'USD' || symbol === '$' ? `$${value}` : `${symbol}${value} ${code}`;
}

function formatTime(value) {
  if (!value) return '';
  try {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
      });
    }
  } catch {}

  if (/^\d{2}:\d{2}$/.test(value)) {
    const [rawHours, rawMinutes] = value.split(':').map(Number);
    const suffix = rawHours >= 12 ? 'PM' : 'AM';
    const hours = rawHours % 12 || 12;
    return `${hours}:${String(rawMinutes).padStart(2, '0')} ${suffix}`;
  }

  return value;
}

function formatDuration(minutes) {
  if (!minutes || Number.isNaN(Number(minutes))) return null;
  const totalMinutes = Number(minutes);
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  if (hours && mins) return `${hours}h ${mins}m`;
  if (hours) return `${hours}h`;
  return `${mins}m`;
}

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeContent(value = '') {
  return String(value)
    .replace(/\[CURRENT_ITINERARY:[\s\S]*$/g, '')
    .replace(/\[FULL_ITINERARY_JSON:[\s\S]*$/g, '')
    .replace(/\r\n/g, '\n')
    .trim();
}

function markdownToHtml(markdown = '') {
  const normalized = normalizeContent(markdown);
  if (!normalized) return '';

  const lines = normalized.split('\n');
  const html = [];
  let listOpen = false;

  const closeList = () => {
    if (listOpen) {
      html.push('</ul>');
      listOpen = false;
    }
  };

  const inlineFormat = (text) => {
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>');
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    return formatted;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }

    if (line.startsWith('### ')) {
      closeList();
      html.push(`<h3>${inlineFormat(line.slice(4))}</h3>`);
      continue;
    }

    if (line.startsWith('## ')) {
      closeList();
      html.push(`<h2>${inlineFormat(line.slice(3))}</h2>`);
      continue;
    }

    if (line.startsWith('# ')) {
      closeList();
      html.push(`<h1>${inlineFormat(line.slice(2))}</h1>`);
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      if (!listOpen) {
        html.push('<ul>');
        listOpen = true;
      }
      html.push(`<li>${inlineFormat(line.replace(/^[-*]\s+/, ''))}</li>`);
      continue;
    }

    closeList();
    html.push(`<p>${inlineFormat(line)}</p>`);
  }

  closeList();
  return html.join('');
}

function buildFlightLines(item) {
  const details = item.details || {};
  const isRoundTrip = details.is_round_trip || details.trip_type === 'round_trip';
  const lines = [];

  if (isRoundTrip) {
    const outboundSegments = details.outbound_segments || [];
    const returnSegments = details.return_segments || [];
    const outboundStart = outboundSegments[0];
    const outboundEnd = outboundSegments[outboundSegments.length - 1];
    const returnStart = returnSegments[0];
    const returnEnd = returnSegments[returnSegments.length - 1];

    if (outboundStart && outboundEnd) {
      lines.push({
        label: 'Outbound',
        value: `${outboundStart.origin || 'TBD'} -> ${outboundEnd.destination || 'TBD'} | ${formatTime(outboundStart.departure_time)} to ${formatTime(outboundEnd.arrival_time)}`,
      });
    }
    if (returnStart && returnEnd) {
      lines.push({
        label: 'Return',
        value: `${returnStart.origin || 'TBD'} -> ${returnEnd.destination || 'TBD'} | ${formatTime(returnStart.departure_time)} to ${formatTime(returnEnd.arrival_time)}`,
      });
    }
    if (details.outbound_duration_minutes || details.return_duration_minutes) {
      lines.push({
        label: 'Travel time',
        value: [
          details.outbound_duration_minutes ? `outbound ${formatDuration(details.outbound_duration_minutes)}` : null,
          details.return_duration_minutes ? `return ${formatDuration(details.return_duration_minutes)}` : null,
        ].filter(Boolean).join(' | '),
      });
    }

    return lines;
  }

  const segments = details.segments || [];
  const first = segments[0];
  const last = segments[segments.length - 1];
  if (first && last) {
    lines.push({
      label: 'Route',
      value: `${first.origin || 'TBD'} -> ${last.destination || 'TBD'} | ${formatTime(first.departure_time)} to ${formatTime(last.arrival_time)}`,
    });
  }
  if (details.total_duration_minutes) {
    lines.push({ label: 'Travel time', value: formatDuration(details.total_duration_minutes) });
  }

  return lines;
}

function buildHotelLines(item) {
  const details = item.details || {};
  const values = [];
  if (item.subtitle) values.push(item.subtitle);
  if (details.nights) values.push(`${details.nights} night${details.nights === 1 ? '' : 's'}`);
  if (details.room_type) values.push(details.room_type);
  if (details.rating) values.push(`${details.rating} star`);
  return values.length ? [{ label: 'Stay', value: values.join(' | ') }] : [];
}

function buildActivityLines(item) {
  const details = item.details || {};
  const lines = [];
  if (item.subtitle) lines.push({ label: 'Plan', value: item.subtitle });
  if (details.city) lines.push({ label: 'City', value: details.city });
  if (details.category) lines.push({ label: 'Category', value: details.category });
  if (details.description) lines.push({ label: 'Notes', value: details.description });
  return lines;
}

function buildItemCards(itinerary) {
  const items = Array.isArray(itinerary?.items) ? itinerary.items : [];
  return items.map((item, index) => {
    const cost = formatCurrency(item.cost, item);
    const common = [];
    if (item.date) common.push({ label: 'Date', value: formatDate(item.date, { month: 'long', day: 'numeric', year: 'numeric' }) });
    if (cost) common.push({ label: 'Estimated cost', value: cost });
    if (item.booking_url) common.push({ label: 'Booking link', value: item.booking_url, isLink: true });

    const typeSpecific =
      item.type === 'flight' ? buildFlightLines(item) :
      item.type === 'hotel' ? buildHotelLines(item) :
      buildActivityLines(item);

    const rows = [...common, ...typeSpecific]
      .map((row) => {
        const value = row.isLink
          ? `<a href="${escapeHtml(row.value)}">${escapeHtml(row.value)}</a>`
          : escapeHtml(row.value);
        return `<div class="detail-row"><div class="detail-label">${escapeHtml(row.label)}</div><div class="detail-value">${value}</div></div>`;
      })
      .join('');

    return `
      <section class="trip-card">
        <div class="card-top">
          <div>
            <div class="eyebrow">${escapeHtml(`${index + 1}. ${item.type || 'item'}`)}</div>
            <h3>${escapeHtml(item.title || 'Untitled item')}</h3>
          </div>
        </div>
        <div class="card-body">
          ${rows || '<p class="muted">No additional details available.</p>'}
        </div>
      </section>
    `;
  }).join('');
}

function buildPrintableHtml(itinerary, assistantContent = '') {
  const items = Array.isArray(itinerary?.items) ? itinerary.items : [];
  const destinations = Array.isArray(itinerary?.destinations) ? itinerary.destinations : [];
  const totalCost = items.reduce(
    (sum, item) => sum + (item.type === 'transit' ? 0 : Number(item.cost || 0)),
    0
  );
  const summaryHtml = markdownToHtml(assistantContent);

  return `
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>${escapeHtml(itinerary.trip_title || 'Trip plan')}</title>
        <style>
          :root {
            --ink: #161616;
            --muted: #5f5f5f;
            --line: #dddddd;
            --surface: #ffffff;
            --surface-alt: #f6f6ef;
            --accent: #d9f23f;
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            color: var(--ink);
            background: #ecebe4;
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            line-height: 1.45;
          }
          .page {
            width: 8.5in;
            margin: 0 auto;
            background: var(--surface);
            padding: 0.7in;
          }
          .hero {
            border: 1px solid var(--line);
            background: linear-gradient(135deg, #fbfbf8 0%, #f3f2e8 100%);
            padding: 28px;
            margin-bottom: 28px;
          }
          .hero h1 {
            margin: 0 0 10px;
            font-size: 28px;
            line-height: 1.15;
          }
          .hero-meta {
            color: var(--muted);
            font-size: 14px;
          }
          .stats {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 18px;
          }
          .stat {
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.75);
            padding: 12px 14px;
          }
          .stat-label {
            color: var(--muted);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 6px;
          }
          .stat-value {
            font-size: 16px;
            font-weight: 700;
          }
          .section-title {
            display: inline-block;
            margin: 20px 0 14px;
            padding: 6px 10px;
            background: var(--accent);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
          }
          .summary {
            margin-bottom: 28px;
          }
          .summary p,
          .summary li {
            font-size: 14px;
            margin: 0 0 10px;
          }
          .summary ul {
            margin: 0 0 12px 18px;
            padding: 0;
          }
          .summary h1,
          .summary h2,
          .summary h3 {
            margin: 18px 0 10px;
            font-size: 18px;
          }
          .summary a,
          .detail-value a {
            color: #0f5cc0;
            text-decoration: underline;
            word-break: break-word;
          }
          .trip-card {
            border: 1px solid var(--line);
            margin-bottom: 16px;
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .card-top {
            padding: 16px 18px 10px;
            border-bottom: 1px solid var(--line);
            background: var(--surface-alt);
          }
          .eyebrow {
            color: var(--muted);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 6px;
          }
          .card-top h3 {
            margin: 0;
            font-size: 20px;
            line-height: 1.2;
          }
          .card-body {
            padding: 14px 18px 18px;
          }
          .detail-row {
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid #efefef;
          }
          .detail-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
          }
          .detail-label {
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
          }
          .detail-value {
            font-size: 14px;
            word-break: break-word;
          }
          .muted {
            color: var(--muted);
            margin: 0;
          }
          @page {
            margin: 0.45in;
            size: letter;
          }
          @media print {
            body {
              background: white;
            }
            .page {
              width: auto;
              margin: 0;
              padding: 0;
            }
          }
        </style>
      </head>
      <body>
        <main class="page">
          <section class="hero">
            <h1>${escapeHtml(itinerary.trip_title || 'Trip plan')}</h1>
            <div class="hero-meta">
              ${escapeHtml(`${formatDate(itinerary.start_date, { month: 'long', day: 'numeric', year: 'numeric' })} - ${formatDate(itinerary.end_date, { month: 'long', day: 'numeric', year: 'numeric' })} | ${itinerary.travelers || 1} traveler${itinerary.travelers === 1 ? '' : 's'}`)}
            </div>
            <div class="stats">
              <div class="stat">
                <div class="stat-label">Destinations</div>
                <div class="stat-value">${escapeHtml(destinations.join(' -> ') || 'TBD')}</div>
              </div>
              <div class="stat">
                <div class="stat-label">Items</div>
                <div class="stat-value">${escapeHtml(String(items.length))}</div>
              </div>
              <div class="stat">
                <div class="stat-label">Estimated total</div>
                <div class="stat-value">${escapeHtml(formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' }) || 'TBD')}</div>
              </div>
            </div>
          </section>

          ${summaryHtml ? `
            <section class="summary">
              <div class="section-title">Trip Summary</div>
              ${summaryHtml}
            </section>
          ` : ''}

          <section>
            <div class="section-title">Trip Details</div>
            ${buildItemCards(itinerary)}
          </section>
        </main>
      </body>
    </html>
  `;
}

export function downloadItineraryPdf(itinerary, assistantContent = '') {
  const html = buildPrintableHtml(itinerary, assistantContent);
  const iframe = document.createElement('iframe');
  iframe.setAttribute('aria-hidden', 'true');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';

  document.body.appendChild(iframe);

  const cleanup = () => {
    setTimeout(() => {
      iframe.remove();
    }, 500);
  };

  let hasPrinted = false;

  const printFrame = iframe.contentWindow;
  if (!printFrame) {
    cleanup();
    return;
  }

  const frameDocument = printFrame.document;
  frameDocument.open();
  frameDocument.write(html);
  frameDocument.close();
  frameDocument.title = `${itinerary?.trip_title || 'Trip plan'} PDF`;

  const triggerPrint = () => {
    if (hasPrinted) return;
    hasPrinted = true;
    printFrame.focus();
    printFrame.print();
  };

  printFrame.onafterprint = cleanup;
  iframe.onload = () => {
    setTimeout(triggerPrint, 150);
  };

  setTimeout(() => {
    if (document.body.contains(iframe)) {
      triggerPrint();
    }
  }, 400);
}
