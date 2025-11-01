import React from "react";
import { motion } from "framer-motion";
import { ArrowRight, Github, BookOpen, Cpu, Cloud, Terminal } from "lucide-react";

// Replace this with your generated hero image path when ready
const HERO_IMG = "/hero-tldw-server.png"; // placeholder path

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-zinc-100 antialiased selection:bg-fuchsia-500/40 selection:text-white">
      {/* NAVBAR */}
      <header className="fixed inset-x-0 top-0 z-50 border-b border-white/10 backdrop-blur-md bg-black/40">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <a href="#top" className="group inline-flex items-center gap-2">
            <div className="h-6 w-6 rounded-lg bg-gradient-to-tr from-fuchsia-500 via-cyan-400 to-violet-600" />
            <span className="font-semibold tracking-tight">tldw_server</span>
          </a>
          <nav className="hidden items-center gap-6 md:flex">
            <a href="#cta" className="text-sm text-zinc-300 hover:text-white">Get Started</a>
            <a href="#about" className="text-sm text-zinc-300 hover:text-white">About</a>
            <a href="#features" className="text-sm text-zinc-300 hover:text-white">Features</a>
            <a href="#faq" className="text-sm text-zinc-300 hover:text-white">FAQ</a>
            <a href="https://github.com/your-org/tldw_server" target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-3 py-1.5 text-sm hover:bg-white/5">
              <Github className="h-4 w-4" />
              <span>GitHub</span>
            </a>
          </nav>
        </div>
      </header>

      {/* HERO */}
      <section id="top" className="relative isolate flex min-h-[92vh] items-end overflow-hidden pt-20">
        {/* Background image / placeholder */}
        <div className="absolute inset-0">
          <div
            className="absolute inset-0 bg-center bg-cover"
            style={{
              backgroundImage: `url(${HERO_IMG})`,
            }}
            aria-hidden
          />
          {/* Fallback gradient overlay when image not yet provided */}
          <div className="absolute inset-0 bg-[radial-gradient(60%_40%_at_50%_0%,rgba(139,92,246,0.25),transparent_70%),radial-gradient(30%_30%_at_80%_40%,rgba(34,211,238,0.25),transparent_70%),radial-gradient(40%_40%_at_20%_80%,rgba(236,72,153,0.2),transparent_70%)]" />
          <div className="absolute inset-0 bg-gradient-to-t from-black via-black/60 to-black/5" />
        </div>

        <div className="relative z-10 mx-auto w-full max-w-6xl px-4 pb-16">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-3xl"
          >
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-1 text-xs text-zinc-300 backdrop-blur">
              <span className="h-2 w-2 rounded-full bg-fuchsia-500 animate-pulse" />
              Inspired by *The Diamond Age* primer
            </div>
            <h1 className="text-4xl font-semibold leading-tight tracking-tight md:text-6xl">
              Your always-on, street-smart primer.
            </h1>
            <p className="mt-4 max-w-2xl text-base text-zinc-300 md:text-lg">
              Placeholder: one-liner describing <strong>tldw_server</strong>-a lightweight, open source service that distills streams into actionable guidance, anywhere.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a href="#cta" className="inline-flex items-center gap-2 rounded-2xl bg-white px-4 py-2 text-sm font-medium text-black hover:bg-zinc-100">
                Get Started <ArrowRight className="h-4 w-4" />
              </a>
              <a href="https://github.com/your-org/tldw_server" target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-black/30 px-4 py-2 text-sm text-white hover:bg-white/5">
                <Github className="h-4 w-4" /> View on GitHub
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section id="cta" className="relative border-t border-white/10 bg-zinc-950/70 py-16">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(50%_50%_at_50%_0%,rgba(139,92,246,0.2),transparent_70%)]" />
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid gap-6 md:grid-cols-3">
            <div className="md:col-span-2">
              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">Quick start</h2>
              <p className="mt-2 max-w-prose text-zinc-300">
                Placeholder: crisp sentence on how to deploy or try the demo. Include docker one-liner or curl command later.
              </p>
            </div>
            <div className="flex items-start justify-start md:justify-end">
              <a href="#about" className="inline-flex items-center gap-2 rounded-2xl bg-fuchsia-500/90 px-5 py-3 text-sm font-medium text-white hover:bg-fuchsia-500">
                Read the overview <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ABOUT */}
      <section id="about" className="border-t border-white/10 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid items-start gap-10 md:grid-cols-2">
            <div>
              <h3 className="text-xl font-semibold tracking-tight md:text-2xl">What is tldw_server?</h3>
              <p className="mt-3 text-zinc-300">
                Placeholder: a few sentences describing the core idea-capture audio/video/streams, summarize, ground in tools, and deliver step-by-step guidance like the Primer.
              </p>
              <p className="mt-3 text-zinc-300">
                Placeholder: note security model, privacy stance, and extensible plugin surface.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-zinc-900 to-zinc-950 p-6 shadow-2xl">
              <ul className="space-y-4 text-sm text-zinc-200">
                <li className="flex items-start gap-3"><Terminal className="mt-0.5 h-5 w-5 text-fuchsia-400" /> Placeholder: CLI and REST endpoints for ingestion and retrieval.</li>
                <li className="flex items-start gap-3"><Cpu className="mt-0.5 h-5 w-5 text-fuchsia-400" /> Placeholder: model-agnostic summarization with retrieval and tool-use.</li>
                <li className="flex items-start gap-3"><Cloud className="mt-0.5 h-5 w-5 text-fuchsia-400" /> Placeholder: self-host or one-click deploy to your infra.</li>
                <li className="flex items-start gap-3"><BookOpen className="mt-0.5 h-5 w-5 text-fuchsia-400" /> Placeholder: examples-classroom tutoring, field manuals, on-the-job primers.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="border-t border-white/10 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <h3 className="text-xl font-semibold tracking-tight md:text-2xl">What's possible</h3>
          <p className="mt-2 max-w-prose text-zinc-300">Placeholder: short paragraph introducing use-cases and extensibility.</p>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              {
                title: "Live mentor",
                desc: "Placeholder: real-time guidance layered on noisy environments.",
              },
              {
                title: "TLDW at scale",
                desc: "Placeholder: summarize long calls and videos with citations.",
              },
              {
                title: "Action loops",
                desc: "Placeholder: connect outputs to automations and tools.",
              },
              {
                title: "Edge-friendly",
                desc: "Placeholder: runs on modest hardware with streaming.",
              },
              {
                title: "Privacy-first",
                desc: "Placeholder: local processing options; bring-your-own-keys.",
              },
              {
                title: "Plugin surface",
                desc: "Placeholder: adapters for ASR, LLMs, vector stores, and UIs.",
              },
            ].map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="rounded-2xl border border-white/10 bg-zinc-900/50 p-5 shadow-lg"
              >
                <h4 className="text-base font-medium">{f.title}</h4>
                <p className="mt-2 text-sm text-zinc-300">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-white/10 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <h3 className="text-xl font-semibold tracking-tight md:text-2xl">FAQ</h3>
          <div className="mt-6 grid gap-6 md:grid-cols-2">
            {[
              {
                q: "Is this production-ready?",
                a: "Placeholder: note current stability, APIs likely to change, roadmap, and contribution guidelines.",
              },
              {
                q: "How is data handled?",
                a: "Placeholder: outline security/privacy posture, logging, encryption, and self-hosting knobs.",
              },
              {
                q: "Which models are supported?",
                a: "Placeholder: list of tested ASR/LLM providers; model-agnostic adapters.",
              },
              {
                q: "Can I contribute?",
                a: "Placeholder: link to CONTRIBUTING.md and good-first-issues.",
              },
            ].map((item, i) => (
              <div key={i} className="rounded-2xl border border-white/10 bg-zinc-900/50 p-5">
                <p className="text-sm font-medium">{item.q}</p>
                <p className="mt-2 text-sm text-zinc-300">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/10 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 md:flex-row">
          <p className="text-xs text-zinc-400">© {new Date().getFullYear()} tldw_server. MIT License.</p>
          <div className="flex items-center gap-4 text-xs text-zinc-400">
            <a href="#about" className="hover:text-white">About</a>
            <a href="#features" className="hover:text-white">Features</a>
            <a href="https://github.com/your-org/tldw_server" target="_blank" rel="noreferrer" className="hover:text-white">GitHub</a>
          </div>
        </div>
      </footer>

      {/* Smooth scroll */}
      <script dangerouslySetInnerHTML={{ __html: `
        document.querySelectorAll('a[href^="#"]').forEach(a=>{
          a.addEventListener('click', e=>{
            const id=a.getAttribute('href');
            if(id.length>1){ e.preventDefault(); document.querySelector(id)?.scrollIntoView({behavior:'smooth',block:'start'}); }
          })
        })
      `}} />
    </div>
  );
}
