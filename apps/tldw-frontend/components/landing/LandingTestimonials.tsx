import React from "react"
import { Quote } from "lucide-react"

interface Testimonial {
  quote: string
  author: string
  role: string
}

interface LandingTestimonialsProps {
  headline: string
  testimonials: Testimonial[]
}

export function LandingTestimonials({ headline, testimonials }: LandingTestimonialsProps) {
  return (
    <section className="py-24 px-6 bg-surface">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">{headline}</h2>

        <div className="grid md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, i) => (
            <div
              key={i}
              className="p-6 bg-bg rounded-xl border border-border"
            >
              <Quote className="w-8 h-8 text-primary/30 mb-4" />
              <p className="text-text-muted mb-6 italic">
                &ldquo;{testimonial.quote}&rdquo;
              </p>
              <div>
                <p className="font-medium">{testimonial.author}</p>
                <p className="text-sm text-text-muted">{testimonial.role}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
