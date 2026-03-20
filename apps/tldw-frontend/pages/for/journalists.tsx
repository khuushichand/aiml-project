import {
  Mic,
  Search,
  FileText,
  Bot,
  Globe,
  Shield,
  Server,
  Eye,
  Lock,
} from "lucide-react"
import {
  LandingLayout,
  LandingHero,
  LandingProblem,
  LandingFeatures,
  LandingTestimonials,
  LandingComparison,
  LandingCTA,
} from "@web/components/landing"

export default function JournalistsPage() {
  const description = "Self-hosted transcription, search, and knowledge management for investigative journalism. Your interviews and research never touch third-party servers."
  return (
    <LandingLayout
      title="tldw for Investigative Journalists"
      description={description}
      segment="journalists"
    >
      <LandingHero
        headline="Your Sources Trust You With Their Safety.\nYour Research Tool Should Deserve That Trust."
        subheadline={description}
        primaryCTA={{ text: "Start Self-Hosting Free", href: "/docs/self-hosting" }}
        secondaryCTA={{ text: "Read the Docs", href: "/docs" }}
      />

      <LandingProblem
        headline="The Tools You Use Are a Liability"
        problems={[
          "Cloud transcription services store your audio on servers you don't control",
          "Your recordings may be used to train AI models without your knowledge",
          "Third-party servers can be subpoenaed without notifying you",
          "Major transcription services have had data breaches—Otter.ai, Rev, Trint",
          "Your source's voice, your questions, your investigation—sitting on someone else's infrastructure",
        ]}
        conclusion="There's a better way."
      />

      <LandingFeatures
        headline="Research Infrastructure You Control"
        features={[
          {
            icon: Mic,
            title: "Transcribe Everything Locally",
            description: "Interviews, leaked recordings, press conferences, court proceedings. State-of-the-art Whisper-based transcription runs on your machine. Nothing leaves your laptop.",
          },
          {
            icon: Search,
            title: "Search Across Your Entire Archive",
            description: "\"Find every time any source mentioned [company name]\"—full-text search plus AI-powered semantic search across all your transcripts, documents, and notes.",
          },
          {
            icon: FileText,
            title: "Ingest Any Format",
            description: "Audio, video, PDFs, leaked documents, web pages, EPUB files. One knowledge base for your entire investigation.",
          },
          {
            icon: Bot,
            title: "AI Analysis Without Exposure",
            description: "Summarize interviews, extract timelines, find contradictions. Use any LLM—local models for maximum security, or your own API keys.",
          },
          {
            icon: Globe,
            title: "Browser Extension",
            description: "Capture and archive web content before it disappears. One click to save articles, social posts, and videos to your research base.",
          },
          {
            icon: Lock,
            title: "Air-Gap Compatible",
            description: "Runs completely offline for maximum security. No network connection required once installed.",
          },
        ]}
      />

      <section className="py-24 px-6 bg-surface">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Built for Paranoid Professionals</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="flex items-start gap-4 p-6 bg-bg rounded-xl border border-border">
              <Shield className="w-8 h-8 text-primary flex-shrink-0" />
              <div>
                <h3 className="font-semibold mb-2">Open Source</h3>
                <p className="text-text-muted">Audit the code yourself. We have nothing to hide.</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-6 bg-bg rounded-xl border border-border">
              <Server className="w-8 h-8 text-primary flex-shrink-0" />
              <div>
                <h3 className="font-semibold mb-2">Self-Hosted</h3>
                <p className="text-text-muted">Runs on your laptop, your server, your rules.</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-6 bg-bg rounded-xl border border-border">
              <Eye className="w-8 h-8 text-primary flex-shrink-0" />
              <div>
                <h3 className="font-semibold mb-2">No Telemetry</h3>
                <p className="text-text-muted">We literally can&apos;t see your data. Check the code.</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-6 bg-bg rounded-xl border border-border">
              <Lock className="w-8 h-8 text-primary flex-shrink-0" />
              <div>
                <h3 className="font-semibold mb-2">Self-Hosted Sync</h3>
                <p className="text-text-muted">Sync notes and files across the infrastructure you control. No hosted tier required.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <LandingTestimonials
        headline="How Journalists Use tldw"
        testimonials={[
          {
            quote: "I had 18 months of interviews—over 200 hours. Before tldw, finding a specific quote meant scrubbing through recordings for hours. Now I search 'defendant mentioned offshore' and get every instance across every interview in seconds.",
            author: "Investigative Reporter",
            role: "Major Metropolitan Daily",
          },
          {
            quote: "When a source gave us 50,000 documents, we needed to process them fast before the story leaked. tldw let us ingest, search, and cross-reference without uploading anything to the cloud. We broke the story in 3 weeks.",
            author: "Editor",
            role: "Nonprofit Investigative Outlet",
          },
          {
            quote: "My source is a whistleblower in an authoritarian country. I can't risk their voice being on any server. tldw lets me transcribe and analyze locally. It's the only tool I trust for this work.",
            author: "Foreign Correspondent",
            role: "International News Organization",
          },
        ]}
      />

      <LandingComparison
        headline="How We Compare"
        competitors={["Otter.ai", "Descript", "Rev.com"]}
        rows={[
          { feature: "AI Transcription", tldw: true, competitors: { "Otter.ai": true, "Descript": true, "Rev.com": true } },
          { feature: "Self-Hosted Option", tldw: true, competitors: { "Otter.ai": false, "Descript": false, "Rev.com": false } },
          { feature: "Semantic Search", tldw: true, competitors: { "Otter.ai": "partial", "Descript": false, "Rev.com": false } },
          { feature: "Document Ingestion", tldw: true, competitors: { "Otter.ai": false, "Descript": false, "Rev.com": false } },
          { feature: "No Cloud Dependency", tldw: true, competitors: { "Otter.ai": false, "Descript": false, "Rev.com": false } },
          { feature: "Open Source", tldw: true, competitors: { "Otter.ai": false, "Descript": false, "Rev.com": false } },
          { feature: "Price", tldw: "Free", competitors: { "Otter.ai": "$100+/mo", "Descript": "$144+/mo", "Rev.com": "$1.50/min" } },
        ]}
      />

      <LandingCTA
        headline="Your Next Investigation Deserves Better Tools"
        description="Stop trusting your most sensitive work to tools that weren't built for it. Get transcription, search, and AI analysis on infrastructure you control."
        primaryCTA={{ text: "Download Self-Hosted", href: "/docs/self-hosting" }}
        secondaryCTA={{ text: "View Documentation", href: "/docs" }}
      />
    </LandingLayout>
  )
}
