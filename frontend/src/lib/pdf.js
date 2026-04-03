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

function sanitizeText(value = '') {
  return String(value)
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/[–—]/g, '-')
    .replace(/…/g, '...')
    .replace(/→/g, ' -> ')
    .replace(/•/g, '- ')
    .replace(/\u00a0/g, ' ')
    .replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '')
    .trim();
}

function escapePdfText(value = '') {
  return sanitizeText(value)
    .replace(/\\/g, '\\\\')
    .replace(/\(/g, '\\(')
    .replace(/\)/g, '\\)');
}

function wrapText(text, maxChars) {
  const clean = sanitizeText(text);
  if (!clean) return [''];

  const paragraphs = clean.split(/\r?\n+/);
  const lines = [];

  for (const paragraph of paragraphs) {
    const words = paragraph.split(/\s+/).filter(Boolean);
    if (!words.length) {
      lines.push('');
      continue;
    }

    let current = '';
    for (const word of words) {
      const candidate = current ? `${current} ${word}` : word;
      if (candidate.length <= maxChars) {
        current = candidate;
        continue;
      }

      if (current) {
        lines.push(current);
      }

      if (word.length <= maxChars) {
        current = word;
        continue;
      }

      let remainder = word;
      while (remainder.length > maxChars) {
        lines.push(remainder.slice(0, maxChars - 1) + '-');
        remainder = remainder.slice(maxChars - 1);
      }
      current = remainder;
    }

    if (current) {
      lines.push(current);
    }
  }

  return lines.length ? lines : [''];
}

function buildFlightSummary(item) {
  const details = item.details || {};
  const isRoundTrip = details.is_round_trip || details.trip_type === 'round_trip';

  if (isRoundTrip) {
    const outboundSegments = details.outbound_segments || [];
    const returnSegments = details.return_segments || [];
    const outboundStart = outboundSegments[0];
    const outboundEnd = outboundSegments[outboundSegments.length - 1];
    const returnStart = returnSegments[0];
    const returnEnd = returnSegments[returnSegments.length - 1];

    const summary = [];
    if (outboundStart && outboundEnd) {
      summary.push(
        `Outbound: ${outboundStart.origin || 'TBD'} -> ${outboundEnd.destination || 'TBD'} | ${formatTime(outboundStart.departure_time)} to ${formatTime(outboundEnd.arrival_time)}`
      );
    }
    if (returnStart && returnEnd) {
      summary.push(
        `Return: ${returnStart.origin || 'TBD'} -> ${returnEnd.destination || 'TBD'} | ${formatTime(returnStart.departure_time)} to ${formatTime(returnEnd.arrival_time)}`
      );
    }
    if (details.outbound_duration_minutes || details.return_duration_minutes) {
      summary.push(
        `Travel time: ${[
          details.outbound_duration_minutes ? `outbound ${formatDuration(details.outbound_duration_minutes)}` : null,
          details.return_duration_minutes ? `return ${formatDuration(details.return_duration_minutes)}` : null,
        ].filter(Boolean).join(' | ')}`
      );
    }
    return summary;
  }

  const segments = details.segments || [];
  const first = segments[0];
  const last = segments[segments.length - 1];
  const summary = [];

  if (first && last) {
    summary.push(
      `Route: ${first.origin || 'TBD'} -> ${last.destination || 'TBD'} | ${formatTime(first.departure_time)} to ${formatTime(last.arrival_time)}`
    );
  }
  if (details.total_duration_minutes) {
    summary.push(`Travel time: ${formatDuration(details.total_duration_minutes)}`);
  }
  return summary;
}

function buildHotelSummary(item) {
  const details = item.details || {};
  const parts = [];
  if (item.subtitle) parts.push(item.subtitle);
  if (details.nights) parts.push(`${details.nights} night${details.nights === 1 ? '' : 's'}`);
  if (details.room_type) parts.push(details.room_type);
  if (details.rating) parts.push(`${details.rating} star`);
  return parts.length ? [`Stay details: ${parts.join(' | ')}`] : [];
}

function buildActivitySummary(item) {
  const details = item.details || {};
  const parts = [];
  if (item.subtitle) parts.push(item.subtitle);
  if (details.city) parts.push(details.city);
  if (details.category) parts.push(details.category);
  if (details.description) parts.push(details.description);
  return parts.length ? [parts.join(' | ')] : [];
}

function itineraryToDocumentSections(itinerary, assistantContent = '') {
  const items = Array.isArray(itinerary?.items) ? itinerary.items : [];
  const destinations = Array.isArray(itinerary?.destinations) ? itinerary.destinations : [];
  const filteredContent = sanitizeText(
    assistantContent
      .replace(/\[CURRENT_ITINERARY:[\s\S]*$/g, '')
      .replace(/\[FULL_ITINERARY_JSON:[\s\S]*$/g, '')
  );

  const totalCost = items.reduce(
    (sum, item) => sum + (item.type === 'transit' ? 0 : Number(item.cost || 0)),
    0
  );

  const sections = [
    { type: 'title', text: itinerary.trip_title || 'Trip plan' },
    {
      type: 'meta',
      text: `${formatDate(itinerary.start_date)} - ${formatDate(itinerary.end_date)} | ${itinerary.travelers || 1} traveler${itinerary.travelers === 1 ? '' : 's'}`,
    },
  ];

  if (destinations.length) {
    sections.push({ type: 'body', text: `Destinations: ${destinations.join(' -> ')}` });
  }

  sections.push({
    type: 'body',
    text: `Estimated total: ${formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' }) || 'TBD'}`,
  });

  if (filteredContent) {
    sections.push({ type: 'section', text: 'Trip Summary' });
    for (const paragraph of filteredContent.split(/\r?\n+/).filter(Boolean)) {
      sections.push({ type: 'body', text: paragraph });
    }
  }

  sections.push({ type: 'section', text: 'Trip Details' });

  items.forEach((item, index) => {
    const cost = formatCurrency(item.cost, item);
    const headingParts = [
      `${index + 1}. ${(item.type || 'item').toUpperCase()}`,
      item.title || 'Untitled item',
    ];
    if (item.date) headingParts.push(`(${formatDate(item.date, { month: 'short', day: 'numeric', year: 'numeric' })})`);
    sections.push({ type: 'itemHeading', text: headingParts.join(' ') });

    const detailRows = [];
    if (cost) detailRows.push(`Estimated cost: ${cost}`);
    if (item.booking_url) detailRows.push(`Booking link: ${item.booking_url}`);

    if (item.type === 'flight') {
      detailRows.push(...buildFlightSummary(item));
    } else if (item.type === 'hotel') {
      detailRows.push(...buildHotelSummary(item));
    } else {
      detailRows.push(...buildActivitySummary(item));
    }

    if (!detailRows.length) {
      detailRows.push('No additional details available.');
    }

    detailRows.forEach((row) => sections.push({ type: 'body', text: row }));
  });

  return sections;
}

function buildPages(sections) {
  const pageWidth = 612;
  const pageHeight = 792;
  const marginX = 54;
  const top = 738;
  const bottom = 54;
  let cursorY = top;
  let currentPage = [];
  const pages = [currentPage];

  const pushLine = (text, options = {}) => {
    const size = options.size || 11;
    const leading = options.leading || size + 4;
    const font = options.font || 'F1';
    const maxChars = options.maxChars || 92;
    const wrapped = wrapText(text, maxChars);

    for (const line of wrapped) {
      if (cursorY - leading < bottom) {
        currentPage = [];
        pages.push(currentPage);
        cursorY = top;
      }

      currentPage.push({
        text: line,
        x: marginX,
        y: cursorY,
        size,
        font,
      });
      cursorY -= leading;
    }
  };

  const addGap = (amount = 10) => {
    cursorY -= amount;
    if (cursorY < bottom) {
      currentPage = [];
      pages.push(currentPage);
      cursorY = top;
    }
  };

  for (const section of sections) {
    if (section.type === 'title') {
      pushLine(section.text, { font: 'F2', size: 20, leading: 28, maxChars: 48 });
      addGap(8);
      continue;
    }

    if (section.type === 'meta') {
      pushLine(section.text, { size: 11, leading: 16, maxChars: 78 });
      addGap(10);
      continue;
    }

    if (section.type === 'section') {
      addGap(6);
      pushLine(section.text, { font: 'F2', size: 14, leading: 20, maxChars: 60 });
      addGap(2);
      continue;
    }

    if (section.type === 'itemHeading') {
      addGap(4);
      pushLine(section.text, { font: 'F2', size: 12, leading: 18, maxChars: 74 });
      continue;
    }

    pushLine(section.text, { size: 11, leading: 15, maxChars: 90 });
  }

  return { pages, pageWidth, pageHeight };
}

function buildPdfBlob(pages, pageWidth, pageHeight) {
  const objects = [];

  const setObject = (index, value) => {
    objects[index - 1] = value;
  };

  const addObject = (value) => {
    objects.push(value);
    return objects.length;
  };

  const catalogId = addObject('');
  const pagesId = addObject('');
  const fontRegularId = addObject('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  const fontBoldId = addObject('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>');

  const pageIds = [];

  pages.forEach((page) => {
    const stream = [
      'BT',
      ...page.map((line) =>
        `/${line.font} ${line.size} Tf 1 0 0 1 ${line.x} ${line.y} Tm (${escapePdfText(line.text)}) Tj`
      ),
      'ET',
    ].join('\n');

    const contentId = addObject(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    const pageId = addObject(
      `<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /Font << /F1 ${fontRegularId} 0 R /F2 ${fontBoldId} 0 R >> >> /Contents ${contentId} 0 R >>`
    );
    pageIds.push(pageId);
  });

  setObject(pagesId, `<< /Type /Pages /Count ${pageIds.length} /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] >>`);
  setObject(catalogId, `<< /Type /Catalog /Pages ${pagesId} 0 R >>`);

  let pdf = '%PDF-1.4\n%\xE2\xE3\xCF\xD3\n';
  const offsets = [0];

  for (let index = 0; index < objects.length; index += 1) {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${objects[index]}\nendobj\n`;
  }

  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += '0000000000 65535 f \n';

  for (let index = 1; index < offsets.length; index += 1) {
    pdf += `${String(offsets[index]).padStart(10, '0')} 00000 n \n`;
  }

  pdf += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;

  return new Blob([pdf], { type: 'application/pdf' });
}

function buildFilename(itinerary) {
  const raw = sanitizeText(itinerary.trip_title || 'trip-plan').toLowerCase();
  const slug = raw
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  return `${slug || 'trip-plan'}.pdf`;
}

export function downloadItineraryPdf(itinerary, assistantContent = '') {
  const sections = itineraryToDocumentSections(itinerary, assistantContent);
  const { pages, pageWidth, pageHeight } = buildPages(sections);
  const blob = buildPdfBlob(pages, pageWidth, pageHeight);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = buildFilename(itinerary);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
