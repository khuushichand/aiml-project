import {
  Video,
  Languages,
  Search,
  GitBranch,
  Wifi,
  Eye,
  Shield,
  Server,
} from "lucide-react"
import {
  LandingLayout,
  LandingHero,
  LandingProblem,
  LandingFeatures,
  LandingTestimonials,
  LandingPricing,
  LandingCTA,
} from "@web/components/landing"

export default function OSINTPage() {
  return (
    <LandingLayout
      title="tldw for OSINT & Threat Intelligence"
      description="Self-hosted transcription, search, and analysis for OSINT professionals. Process Telegram videos, social media, and open source content—air-gapped."
      segment="osint"
    >
      <LandingHero
        headline="Media Intelligence Without the Exposure"
        subheadline="Self-hosted transcription, search, and analysis for OSINT professionals. Process Telegram videos, social media, and open source content—air-gapped."
        primaryCTA={{ text: "Deploy Self-Hosted", href: "/docs/self-hosting" }}
        secondaryCTA={{ text: "View on GitHub", href: "https://github.com/rmusser01/tldw" }}
        badges={["Air-Gap Compatible", "Open Source", "No Telemetry"]}
      />

      <LandingProblem
        headline="Your Tradecraft Stops at Your Tools"
        problems={[
          "You use Tor and compartmentalize identities, then upload collection materials to cloud services",
          "Cloud transcription services log everything and have unknown data retention policies",
          "Your targets might be monitoring these commercial platforms",
          "Your clients expect discretion that SaaS tools can't guarantee",
          "Your current tooling is a gap in your operational security",
        ]}
        conclusion="Close the gap."
      />

      <LandingFeatures
        headline="Collection and Analysis on Your Infrastructure"
        features={[
          {
            icon: Video,
            title: "Ingest Any Media",
            description: "Telegram videos, TikTok, YouTube, podcasts, intercepted audio. Bulk download with yt-dlp integration, automatic transcription. Process hundreds of videos overnight.",
          },
          {
            icon: Languages,
            title: "Multilingual Transcription",
            description: "Whisper-based models handle 99 languages. Russian, Ukrainian, Arabic, Mandarin—transcribe and search in original or translated.",
          },
          {
            icon: Search,
            title: "Search Your Entire Collection",
            description: "\"Find all videos mentioning [location]\" or \"When did [callsign] first appear?\"—full-text and semantic search across all ingested content.",
          },
          {
            icon: GitBranch,
            title: "Build Timelines and Cross-Reference",
            description: "Query across sources. Identify patterns. Connect what Subject A said on Telegram to what appeared on VK a week later.",
          },
          {
            icon: Wifi,
            title: "Air-Gap Compatible",
            description: "Runs completely offline. No telemetry. No cloud dependency. Deploy on isolated infrastructure for maximum security.",
          },
          {
            icon: Eye,
            title: "Audit the Code Yourself",
            description: "Open source means you can verify there are no backdoors. We don't ask you to trust us—we ask you to verify.",
          },
        ]}
      />

      <LandingTestimonials
        headline="Built for the Work You Actually Do"
        testimonials={[
          {
            quote: "We processed 2,000 Telegram videos in a week tracking a conflict zone. Manually, that would have taken months. The multilingual transcription handles Ukrainian and Russian seamlessly.",
            author: "Analyst",
            role: "NGO Conflict Monitor",
          },
          {
            quote: "I can tell you every time a target CEO mentioned a specific topic in the last 5 years of earnings calls, conference talks, and podcasts—with timestamps and context.",
            author: "Competitive Intelligence Professional",
            role: "Consulting Firm",
          },
          {
            quote: "The client had 50 hours of recorded meetings for a due diligence investigation. We turned it around in 48 hours without any of it touching cloud infrastructure.",
            author: "Director",
            role: "Investigative Consultancy",
          },
        ]}
      />

      {/* Security Trust Section */}
      <section className="py-24 px-6 bg-surface">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-12">Security You Can Verify</h2>

          <div className="grid md:grid-cols-3 gap-8 text-left">
            <div className="p-6 bg-bg rounded-xl border border-border">
              <Shield className="w-8 h-8 text-primary mb-4" />
              <h3 className="font-semibold mb-3">Open Source</h3>
              <p className="text-text-muted text-sm">
                Audit the code. Verify there are no backdoors. Fork and modify for your operational requirements.
              </p>
            </div>
            <div className="p-6 bg-bg rounded-xl border border-border">
              <Server className="w-8 h-8 text-primary mb-4" />
              <h3 className="font-semibold mb-3">Self-Hosted</h3>
              <p className="text-text-muted text-sm">
                Your infrastructure. Your rules. Your responsibility. Deploy on air-gapped systems if your threat model requires it.
              </p>
            </div>
            <div className="p-6 bg-bg rounded-xl border border-border">
              <Eye className="w-8 h-8 text-primary mb-4" />
              <h3 className="font-semibold mb-3">No Telemetry</h3>
              <p className="text-text-muted text-sm">
                We can&apos;t see what you&apos;re processing because we never built the capability. Check the code yourself.
              </p>
            </div>
          </div>
        </div>
      </section>

      <LandingPricing
        headline="Pricing"
        tiers={[
          {
            name: "Self-Hosted",
            price: "Free",
            period: "forever",
            description: "Full functionality, no restrictions",
            features: [
              "Unlimited transcription",
              "99 language support",
              "Full search and RAG",
              "Air-gap compatible",
              "Community support",
            ],
            cta: { text: "Clone from GitHub", href: "https://github.com/rmusser01/tldw" },
          },
          {
            name: "Professional",
            price: "$99",
            period: "month",
            description: "For consultancies and teams",
            features: [
              "Priority support",
              "Deployment assistance",
              "Custom integrations",
              "Training sessions",
            ],
            cta: { text: "Contact Us", href: "/contact" },
            highlighted: true,
          },
          {
            name: "Enterprise",
            price: "Custom",
            description: "For organizations with specific requirements",
            features: [
              "On-site deployment",
              "Security review support",
              "Custom development",
              "SLA available",
            ],
            cta: { text: "Contact Us", href: "/contact" },
          },
        ]}
      />

      <LandingCTA
        headline="Your Collection Deserves Better Tooling"
        description="Stop compromising your operational security with cloud-dependent tools. Get the analysis capabilities you need on infrastructure you control."
        primaryCTA={{ text: "Deploy Now", href: "/docs/self-hosting" }}
        secondaryCTA={{ text: "View Source", href: "https://github.com/rmusser01/tldw" }}
      />
    </LandingLayout>
  )
}
