<script>
  import '../app.css';

  // ─── State ───────────────────────────────────────────────────────────────────
  let channelName = '';
  let timeframe = '1_month';

  // Possible phases: 'idle' | 'loading' | 'complete' | 'error'
  let phase = 'idle';

  let progress = 0;
  let statusText = '';
  let results = null;  // { channel, total_trades, win_rate, edge_ratio, color_grade }

  // ─── WebSocket Logic ─────────────────────────────────────────────────────────
  function startAudit() {
    if (!channelName.trim()) return;

    // Reset
    phase = 'loading';
    progress = 0;
    statusText = 'Initialising connection...';
    results = null;

    const ws = new WebSocket('ws://127.0.0.1:8000/api/ws/audit');

    ws.onopen = () => {
      ws.send(JSON.stringify({
        channel_name: channelName.trim(),
        timeframe: timeframe
      }));
    };

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      progress = payload.progress ?? progress;
      statusText = payload.status ?? statusText;

      if (payload.progress === 100 && payload.results) {
        results = payload.results;
        phase = 'complete';
        ws.close();
      } else if (payload.status && payload.status.startsWith('FATAL ERROR')) {
        phase = 'error';
        ws.close();
      }
    };

    ws.onerror = () => {
      statusText = 'WebSocket error — is the backend running?';
      phase = 'error';
    };

    ws.onclose = () => {
      if (phase === 'loading') {
        phase = 'error';
        statusText = 'Connection closed unexpectedly.';
      }
    };
  }

  // ─── Helpers ─────────────────────────────────────────────────────────────────
  const timeframeOptions = [
    { value: '1_month',  label: '1 Month'  },
    { value: '3_months', label: '3 Months' },
    { value: '6_months', label: '6 Months' },
  ];

  $: gradeIsGreen  = results?.color_grade === 'green';
  $: cardClass     = gradeIsGreen ? 'card-green' : 'card-red';
  $: gradeAccent   = gradeIsGreen ? 'text-green-400' : 'text-red-400';
  $: gradeBg       = gradeIsGreen ? 'from-green-500/10 to-transparent' : 'from-red-500/10 to-transparent';
  $: borderColor   = gradeIsGreen ? 'rgba(34,197,94,0.7)' : 'rgba(239,68,68,0.7)';
</script>

<!-- ─── Root ──────────────────────────────────────────────────────────────── -->
<div class="min-h-screen bg-slate-900 flex flex-col items-center px-4 pb-20">

  <!-- ══════════════════════════════════════════════════════════════════ HEADER -->
  <header class="w-full max-w-4xl pt-10 pb-8 flex items-center justify-between border-b border-slate-700/50">
    <div class="flex flex-col">
      <span class="font-mono text-xs tracking-[0.3em] text-slate-500 uppercase mb-1">
        Admin Terminal v2.0
      </span>
      <h1 class="font-sans text-2xl font-bold tracking-tight text-slate-100">
        Kattalan
        <span class="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">
          Quant Engine
        </span>
      </h1>
    </div>

    <!-- System Online indicator -->
    <div class="flex items-center gap-2.5 bg-slate-800/60 border border-slate-700/60 rounded-full px-4 py-2">
      <div class="dot-online"></div>
      <span class="font-mono text-xs text-green-400 tracking-widest uppercase">System Online</span>
    </div>
  </header>

  <!-- ════════════════════════════════════════════════════════════ GRID LAYOUT -->
  <main class="w-full max-w-4xl mt-10 flex flex-col gap-6">

    <!-- ─────────────────────────────────────── decorative ticker strip ──── -->
    <div class="scanner-line w-full border border-slate-800 rounded-lg bg-slate-800/30 px-5 py-2.5 flex gap-8 overflow-hidden">
      {#each ['NSE', 'BSE', 'NIFTY50', 'BANKNIFTY', 'GOLD', 'SENSEX', 'USDINR'] as sym}
        <span class="font-mono text-xs text-slate-500 whitespace-nowrap">
          {sym} <span class="text-slate-600">·</span>
          <span class="text-green-500/70">{(Math.random() * 5 + 0.1).toFixed(2)}%</span>
        </span>
      {/each}
    </div>

    <!-- ════════════════════════════════════════════════════════ INPUT ZONE -->
    <section class="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-6 backdrop-blur-sm">
      <div class="mb-5">
        <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-1">
          &gt; CHANNEL_AUDIT_INIT
        </p>
        <p class="font-sans text-sm text-slate-400">
          Enter a public Telegram channel name and select a lookback window to begin the AI evaluation.
        </p>
      </div>

      <div class="flex flex-col sm:flex-row gap-3">
        <!-- Search bar -->
        <div class="relative flex-1">
          <span class="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-slate-500 text-sm select-none">@</span>
          <input
            id="channel-input"
            type="text"
            bind:value={channelName}
            placeholder="channel_username"
            disabled={phase === 'loading'}
            class="w-full bg-slate-900 border border-slate-600/70 rounded-lg pl-8 pr-4 py-3
                   font-mono text-sm text-slate-100 placeholder-slate-600
                   focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500/60
                   disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          />
        </div>

        <!-- Timeframe dropdown -->
        <div class="relative">
          <select
            id="timeframe-select"
            bind:value={timeframe}
            disabled={phase === 'loading'}
            class="appearance-none bg-slate-900 border border-slate-600/70 rounded-lg
                   px-4 pr-9 py-3 font-mono text-sm text-slate-300
                   focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500/60
                   disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 cursor-pointer"
          >
            {#each timeframeOptions as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
          <!-- custom chevron -->
          <svg class="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        <!-- Audit button -->
        <button
          id="audit-btn"
          on:click={startAudit}
          disabled={phase === 'loading' || !channelName.trim()}
          class="relative px-6 py-3 rounded-lg font-mono text-sm font-semibold tracking-wider uppercase
                 bg-gradient-to-r from-sky-500 to-violet-600 text-white
                 hover:from-sky-400 hover:to-violet-500
                 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed
                 transition-all duration-300 shadow-lg hover:shadow-sky-500/30
                 active:scale-95 whitespace-nowrap"
        >
          {#if phase === 'loading'}
            <svg class="w-4 h-4 animate-spin inline-block mr-2 -mt-0.5" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            Auditing...
          {:else}
            &#9654; Audit Channel
          {/if}
        </button>
      </div>
    </section>

    <!-- ════════════════════════════════════════ LIVE LOADING STATE ══════════ -->
    {#if phase === 'loading' || phase === 'error'}
      <section class="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 backdrop-blur-sm">
        <!-- Terminal header -->
        <div class="flex items-center gap-2 mb-4">
          <div class="w-2.5 h-2.5 rounded-full bg-red-500/80"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-green-500/80"></div>
          <span class="font-mono text-xs text-slate-600 ml-2 tracking-widest">KATTALAN_ENGINE — AUDIT_LOG</span>
        </div>

        <!-- Progress bar track -->
        <div class="w-full h-2 bg-slate-700/60 rounded-full overflow-hidden mb-4">
          {#if phase === 'error'}
            <div class="h-full bg-red-500 rounded-full transition-all duration-500"
                 style="width: {progress}%"></div>
          {:else}
            <div class="h-full rounded-full progress-shimmer transition-all duration-500"
                 style="width: {progress}%"></div>
          {/if}
        </div>

        <!-- Progress percentage + status -->
        <div class="flex items-baseline justify-between">
          <p class="font-mono text-xs {phase === 'error' ? 'text-red-400' : 'text-sky-400'} tracking-wide">
            &gt; {statusText}
          </p>
          <span class="font-mono text-lg font-bold {phase === 'error' ? 'text-red-400/80' : 'text-slate-300'}">
            {progress}<span class="text-xs text-slate-500">%</span>
          </span>
        </div>

        <!-- Animated scan lines when loading -->
        {#if phase === 'loading'}
          <div class="mt-4 space-y-1.5">
            {#each [1,2,3] as i}
              <div class="h-1 rounded bg-slate-700/40 overflow-hidden">
                <div class="h-full w-1/3 bg-gradient-to-r from-transparent via-sky-500/20 to-transparent
                            animate-[scan_2s_ease-in-out_{i * 0.3}s_infinite]"></div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    <!-- ════════════════════════════════════════════ RESULTS CARD ═══════════ -->
    {#if phase === 'complete' && results}
      <section
        class="fade-in border rounded-2xl p-6 backdrop-blur-sm relative overflow-hidden {cardClass}"
        style="background: linear-gradient(135deg, {gradeIsGreen ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)'} 0%, rgba(15,23,42,0.95) 60%)"
      >
        <!-- Top accent bar -->
        <div class="absolute top-0 left-0 right-0 h-px"
             style="background: linear-gradient(90deg, transparent, {borderColor}, transparent)"></div>

        <!-- Header row -->
        <div class="flex items-start justify-between mb-6">
          <div>
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-1">
              // AUDIT_RESULT — COMPLETE
            </p>
            <h2 class="font-mono text-xl font-bold text-slate-100">
              @{results.channel}
            </h2>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span class="font-mono text-xs uppercase tracking-widest {gradeAccent}">
              {gradeIsGreen ? '▲ EDGE POSITIVE' : '▼ EDGE NEGATIVE'}
            </span>
            <div class="w-2.5 h-2.5 rounded-full {gradeIsGreen ? 'bg-green-400' : 'bg-red-400'}"
                 style="box-shadow: 0 0 8px {gradeIsGreen ? 'rgba(34,197,94,0.9)' : 'rgba(239,68,68,0.9)'}"></div>
          </div>
        </div>

        <!-- Stats grid -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">

          <!-- Trades Evaluated -->
          <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-4">
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-2">
              Trades Evaluated
            </p>
            <p class="font-mono text-3xl font-bold text-slate-100 tabular-nums">
              {results.total_trades}
            </p>
          </div>

          <!-- Win Rate -->
          <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-4">
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-2">
              Win Rate
            </p>
            <p class="font-mono text-3xl font-bold {gradeAccent} tabular-nums">
              {results.win_rate}
            </p>
          </div>

          <!-- Edge Ratio -->
          <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-4">
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-2">
              Edge Ratio
            </p>
            <p class="font-mono text-3xl font-bold {gradeAccent} tabular-nums">
              {results.edge_ratio > 0 ? '+' : ''}{results.edge_ratio}
            </p>
          </div>
        </div>

        <!-- Footer note -->
        <div class="mt-5 pt-4 border-t border-slate-700/40 flex items-center justify-between">
          <span class="font-mono text-xs text-slate-600">
            Saved to Supabase · {new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
          </span>
          <button
            on:click={() => { phase = 'idle'; results = null; channelName = ''; }}
            class="font-mono text-xs text-slate-500 hover:text-sky-400 transition-colors duration-200 underline underline-offset-2"
          >
            &#8635; New Audit
          </button>
        </div>
      </section>
    {/if}

  </main>

  <!-- ═══════════════════════════════════════════════════════════════ FOOTER -->
  <footer class="w-full max-w-4xl mt-auto pt-12 border-t border-slate-800/60 flex justify-between items-center">
    <span class="font-mono text-xs text-slate-700 tracking-widest uppercase">
      Kattalan Engine © {new Date().getFullYear()}
    </span>
    <span class="font-mono text-xs text-slate-700">
      ws://127.0.0.1:8000/api/ws/audit
    </span>
  </footer>

</div>
