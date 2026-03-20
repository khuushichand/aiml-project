import {
  Mic,
  Search,
  BookOpen,
  Shield,
  FileOutput,
  Building2,
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

export default function ResearchersPage() {
  const description = "Self-hosted AI transcription and semantic search for qualitative research. IRB-compliant by design—your participant data never leaves your infrastructure."
  return (
    <LandingLayout
      title="tldw for Academic Researchers"
      description={description}
      segment="researchers"
    >
      <LandingHero
        headline="Your Research Data Deserves Better Than\n$1.50/Minute Transcription and NVivo"
        subheadline={description}
        primaryCTA={{ text: "Start Self-Hosting Free", href: "/docs/self-hosting" }}
        secondaryCTA={{ text: "View Documentation", href: "/docs" }}
        badges={["Open Source", "IRB Compliant", "Self-Hosted"]}
      />

      <LandingProblem
        headline="Qualitative Research Tools Are Stuck in 2010"
        problems={[
          "Pay grad students $15/hour for weeks of transcription with inevitable errors",
          "Cloud services like Rev/Otter cost $1-3/minute and may violate your IRB protocol",
          "NVivo and Atlas.ti cost $1,000+ with clunky interfaces and no AI capabilities",
          "ChatGPT can't ingest your entire corpus and has privacy policies incompatible with IRB",
          "You're drowning in PDFs, manually coding transcripts like it's 1995",
        ]}
        conclusion="Your research deserves modern tools that respect your constraints."
      />

      <LandingFeatures
        headline="AI-Powered Research Infrastructure on Your Terms"
        features={[
          {
            icon: Mic,
            title: "Transcribe Interviews in Minutes",
            description: "State-of-the-art speech recognition handles accents, crosstalk, and domain jargon. Process a 1-hour interview in ~5 minutes. Runs locally—your IRB will thank you.",
          },
          {
            icon: BookOpen,
            title: "Build a Searchable Literature Base",
            description: "Ingest papers, books, reports, videos. Ask questions across your entire corpus. \"What do scholars say about [concept]?\"—get answers with citations.",
          },
          {
            icon: Search,
            title: "Query Across All Your Data",
            description: "\"Find everywhere participants mentioned 'barriers to access'\"—semantic search understands meaning, not just keywords. Cross-reference themes across interviews.",
          },
          {
            icon: Building2,
            title: "Self-Hosted = IRB Compliant",
            description: "Runs on your laptop or university server. No data leaves your infrastructure. Perfect for sensitive populations, embargoed research, or paranoid PIs.",
          },
          {
            icon: FileOutput,
            title: "Export Anywhere",
            description: "Transcripts to Word, data to CSV, citations to Zotero. Works with your existing workflow, not against it.",
          },
          {
            icon: Shield,
            title: "University IT Approved",
            description: "Open source code for security review. Deploy on university infrastructure. No external dependencies required.",
          },
        ]}
      />

      <LandingTestimonials
        headline="Trusted by Researchers Who Care About Their Data"
        testimonials={[
          {
            quote: "I transcribed 60 interviews for my dissertation in a weekend. My committee couldn't believe I'd processed that much data. tldw paid for itself in the first hour of grad student labor it saved.",
            author: "PhD Candidate, Sociology",
            role: "R1 University",
          },
          {
            quote: "We study vulnerable populations. Cloud transcription was never an option. tldw lets us use modern AI tools while keeping participant data on university infrastructure. It's exactly what we needed.",
            author: "Associate Professor, Public Health",
            role: "Research University",
          },
          {
            quote: "The semantic search changed how I do lit reviews. I can actually ask questions across hundreds of papers instead of ctrl+F through PDFs.",
            author: "Postdoctoral Researcher",
            role: "Political Science",
          },
        ]}
      />

      <LandingComparison
        headline="How We Compare"
        competitors={["NVivo", "Otter.ai", "Manual Transcription"]}
        rows={[
          { feature: "AI Transcription", tldw: true, competitors: { "NVivo": false, "Otter.ai": true, "Manual Transcription": false } },
          { feature: "Self-Hosted", tldw: true, competitors: { "NVivo": "partial", "Otter.ai": false, "Manual Transcription": true } },
          { feature: "IRB Compliant", tldw: true, competitors: { "NVivo": true, "Otter.ai": "partial", "Manual Transcription": true } },
          { feature: "Semantic Search", tldw: true, competitors: { "NVivo": false, "Otter.ai": false, "Manual Transcription": false } },
          { feature: "Literature Management", tldw: true, competitors: { "NVivo": false, "Otter.ai": false, "Manual Transcription": false } },
          { feature: "Price", tldw: "Free", competitors: { "NVivo": "$1,000+", "Otter.ai": "$100+/mo", "Manual Transcription": "$15/hr" } },
        ]}
      />

      <LandingCTA
        headline="Your Research Deserves Modern Tools"
        description="Stop paying for transcription by the minute or struggling with decade-old software. Get AI-powered research infrastructure on your own terms."
        primaryCTA={{ text: "Download Free", href: "/docs/self-hosting" }}
        secondaryCTA={{ text: "Read the Docs", href: "/docs" }}
      />
    </LandingLayout>
  )
}
