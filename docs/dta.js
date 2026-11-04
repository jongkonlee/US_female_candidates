/* Minimal Stata .dta writer, format 118 (Stata 14 and later). No dependencies.
   cols: [{name, label, type}] where type is 'str', 'byte', 'long', 'double' or 'date' (YYYY-MM-DD -> %td)
   rows: array of arrays (same order as cols). Returns a Uint8Array. */
(function (global) {
  'use strict';
  const enc = new TextEncoder();
  const T_STRL = 32768, T_DOUBLE = 65526, T_LONG = 65528, T_BYTE = 65530;
  const MISS_BYTE = 101, MISS_LONG = 2147483621;

  class Buf {
    constructor(n) { this.a = new Uint8Array(n || 1 << 16); this.n = 0; this.v = new DataView(this.a.buffer); }
    need(k) {
      if (this.n + k <= this.a.length) return;
      let m = this.a.length * 2; while (m < this.n + k) m *= 2;
      const b = new Uint8Array(m); b.set(this.a.subarray(0, this.n)); this.a = b; this.v = new DataView(b.buffer);
    }
    bytes(u8) { this.need(u8.length); this.a.set(u8, this.n); this.n += u8.length; }
    ascii(s) { this.bytes(enc.encode(s)); }
    u8(x) { this.need(1); this.v.setUint8(this.n, x); this.n += 1; }
    i8(x) { this.need(1); this.v.setInt8(this.n, x); this.n += 1; }
    u16(x) { this.need(2); this.v.setUint16(this.n, x, true); this.n += 2; }
    u32(x) { this.need(4); this.v.setUint32(this.n, x, true); this.n += 4; }
    i32(x) { this.need(4); this.v.setInt32(this.n, x, true); this.n += 4; }
    u64(x) { this.need(8); this.v.setUint32(this.n, x % 4294967296, true); this.v.setUint32(this.n + 4, Math.floor(x / 4294967296), true); this.n += 8; }
    f64(x) { this.need(8); this.v.setFloat64(this.n, x, true); this.n += 8; }
    fixed(u8, w) { this.need(w); const k = Math.min(u8.length, w); this.a.set(u8.subarray(0, k), this.n); this.a.fill(0, this.n + k, this.n + w); this.n += w; }
    set64(pos, x) { this.v.setUint32(pos, x % 4294967296, true); this.v.setUint32(pos + 4, Math.floor(x / 4294967296), true); }
  }

  function cut(u8, maxBytes) {            // cut UTF-8 bytes without splitting a character
    if (u8.length <= maxBytes) return u8;
    let k = maxBytes; while (k > 0 && (u8[k] & 0xC0) === 0x80) k--;
    return u8.subarray(0, k);
  }
  const EPOCH = Date.UTC(1960, 0, 1);
  function tdays(s) {
    if (!s || typeof s !== 'string' || s.length < 10) return null;
    const t = Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
    return isNaN(t) ? null : Math.round((t - EPOCH) / 86400000);
  }
  function stataName(s, used) {
    let n = String(s).replace(/[^A-Za-z0-9_]/g, '_').slice(0, 32);
    if (!/^[A-Za-z_]/.test(n)) n = ('v_' + n).slice(0, 32);
    let k = n, i = 2; while (used.has(k)) { k = (n.slice(0, 28) + '_' + i++); } used.add(k); return k;
  }

  function writeDta(cols, rows, dataLabel) {
    const K = cols.length, N = rows.length, used = new Set();
    const spec = cols.map((c, j) => {
      const s = { name: stataName(c.name, used), label: c.label || '', kind: c.type || 'str' };
      if (s.kind === 'str') {
        let w = 1;
        const vals = rows.map(r => { const v = r[j]; const u = (v === null || v === undefined) ? new Uint8Array(0) : enc.encode(String(v)); if (u.length > w) w = u.length; return u; });
        s.vals = vals;
        if (w > 2045) { s.type = T_STRL; s.width = 8; s.fmt = '%9s'; } else { s.type = w; s.width = w; s.fmt = '%' + Math.min(w, 60) + 's'; }
      } else if (s.kind === 'byte') { s.type = T_BYTE; s.width = 1; s.fmt = '%8.0g'; }
      else if (s.kind === 'long') { s.type = T_LONG; s.width = 4; s.fmt = '%12.0g'; }
      else if (s.kind === 'date') { s.type = T_LONG; s.width = 4; s.fmt = '%td'; }
      else { s.type = T_DOUBLE; s.width = 8; s.fmt = '%10.0g'; }
      return s;
    });
    const b = new Buf(1 << 20);
    const map = new Array(14).fill(0);
    b.ascii('<stata_dta>');
    b.ascii('<header><release>118</release><byteorder>LSF</byteorder>');
    b.ascii('<K>'); b.u16(K); b.ascii('</K>');
    b.ascii('<N>'); b.u64(N); b.ascii('</N>');
    const lab = cut(enc.encode(dataLabel || ''), 320);
    b.ascii('<label>'); b.u16(lab.length); b.bytes(lab); b.ascii('</label>');
    const d = new Date(), mon = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];
    const ts = String(d.getDate()).padStart(2, '0') + ' ' + mon + ' ' + d.getFullYear() + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    b.ascii('<timestamp>'); b.u8(17); b.ascii(ts); b.ascii('</timestamp></header>');
    map[1] = b.n; b.ascii('<map>'); const mapPos = b.n; for (let i = 0; i < 14; i++) b.u64(0); b.ascii('</map>');
    map[2] = b.n; b.ascii('<variable_types>'); spec.forEach(s => b.u16(s.type)); b.ascii('</variable_types>');
    map[3] = b.n; b.ascii('<varnames>'); spec.forEach(s => b.fixed(enc.encode(s.name), 129)); b.ascii('</varnames>');
    map[4] = b.n; b.ascii('<sortlist>'); for (let i = 0; i <= K; i++) b.u16(0); b.ascii('</sortlist>');
    map[5] = b.n; b.ascii('<formats>'); spec.forEach(s => b.fixed(enc.encode(s.fmt), 57)); b.ascii('</formats>');
    map[6] = b.n; b.ascii('<value_label_names>'); spec.forEach(() => b.fixed(new Uint8Array(0), 129)); b.ascii('</value_label_names>');
    map[7] = b.n; b.ascii('<variable_labels>'); spec.forEach(s => b.fixed(cut(enc.encode(s.label), 320), 321)); b.ascii('</variable_labels>');
    map[8] = b.n; b.ascii('<characteristics></characteristics>');
    map[9] = b.n; b.ascii('<data>');
    const gso = [];
    for (let i = 0; i < N; i++) {
      const r = rows[i];
      for (let j = 0; j < K; j++) {
        const s = spec[j], v = r[j];
        if (s.kind === 'str') {
          const u = s.vals[i];
          if (s.type === T_STRL) {
            if (u.length === 0) { b.u16(0); b.u16(0); b.u32(0); }
            else { const o = i + 1; b.u16(j + 1); b.u16(o % 65536); b.u32(Math.floor(o / 65536)); gso.push([j + 1, o, u]); }
          } else b.fixed(u, s.width);
        } else if (s.kind === 'byte') {
          const x = (v === null || v === undefined || v === '' || isNaN(+v)) ? null : Math.round(+v);
          b.i8(x === null || x > 100 || x < -127 ? MISS_BYTE : x);
        } else if (s.kind === 'long' || s.kind === 'date') {
          const x = s.kind === 'date' ? tdays(v) : ((v === null || v === undefined || v === '' || isNaN(+v)) ? null : Math.round(+v));
          b.i32(x === null || x > 2147483620 || x < -2147483647 ? MISS_LONG : x);
        } else {
          const x = (v === null || v === undefined || v === '' || isNaN(+v)) ? null : +v;
          if (x === null) { b.need(8); b.v.setUint32(b.n, 0, true); b.v.setUint32(b.n + 4, 0x7FE00000, true); b.n += 8; }
          else b.f64(x);
        }
      }
    }
    b.ascii('</data>');
    map[10] = b.n; b.ascii('<strls>');
    gso.forEach(([vv, o, u]) => { b.ascii('GSO'); b.u32(vv); b.u64(o); b.u8(130); b.u32(u.length + 1); b.bytes(u); b.u8(0); });
    b.ascii('</strls>');
    map[11] = b.n; b.ascii('<value_labels></value_labels>');
    map[12] = b.n; b.ascii('</stata_dta>');
    map[13] = b.n;
    for (let i = 0; i < 14; i++) b.set64(mapPos + 8 * i, map[i]);
    return b.a.slice(0, b.n);
  }
  global.writeDta = writeDta;
  if (typeof module !== 'undefined') module.exports = { writeDta };
})(typeof window !== 'undefined' ? window : globalThis);
