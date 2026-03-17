"use client";

import { useState, useMemo } from "react";

import Navbar from "@/app/components/navbar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m21 21-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function TicketIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 010-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375z"
      />
    </svg>
  );
}

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
      />
    </svg>
  );
}

function CreditCardIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z"
      />
    </svg>
  );
}

function EnvelopeIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
      />
    </svg>
  );
}

function PhoneIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"
      />
    </svg>
  );
}

function ChatBubbleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"
      />
    </svg>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

type FaqCategory = "Ticketing" | "Events" | "Payments";

interface FaqItem {
  question: string;
  answer: string;
  category: FaqCategory;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    question: "How do I create an event?",
    answer:
      'To create an event, click "Create Event" in the navigation bar. Fill out the event details including title, description, date, time, location, and ticket information. You can add images, a schedule, and set your pricing. Once you\'re ready, click "Publish Event" to make it live.',
    category: "Events",
  },
  {
    question: "How do I purchase tickets?",
    answer:
      "Browse events on the home page or search for specific events. Click on an event to view its details, then select the number of tickets you'd like and click \"Get Tickets\". You'll be guided through a secure checkout process to complete your purchase.",
    category: "Ticketing",
  },
  {
    question: "What payment methods are accepted?",
    answer:
      "We accept all major credit cards, PayPal, and Apple Pay. Payment processing is secure and handled through our trusted payment partners.",
    category: "Payments",
  },
  {
    question: "How do I cancel or refund tickets?",
    answer:
      'You can request a cancellation or refund from your "My Tickets" page. Select the ticket you want to cancel and click "Request Refund". Refunds are processed according to the event organizer\'s refund policy, typically within 5-10 business days.',
    category: "Ticketing",
  },
  {
    question: "Can I transfer my tickets to someone else?",
    answer:
      'Yes! Go to "My Tickets", select the ticket you want to transfer, and click "Transfer Ticket". Enter the recipient\'s email address and they\'ll receive instructions to claim the ticket. Transfers are free and instant.',
    category: "Ticketing",
  },
  {
    question: "How do I contact the event organizer?",
    answer:
      "On the event details page, you'll find the organizer's information in the sidebar. Click on the organizer's name to view their profile, or use the \"Contact Organizer\" button to send them a direct message through our platform.",
    category: "Events",
  },
  {
    question: "How do I set up ticket pricing?",
    answer:
      "When creating an event, you can set ticket prices in the Pricing & Capacity section. You can offer free tickets by setting the price to $0, or set a specific price. Multiple ticket tiers will be supported in a future update.",
    category: "Payments",
  },
  {
    question: "Are there any fees for selling tickets?",
    answer:
      "Evently charges a small service fee on paid tickets to cover payment processing and platform maintenance. Free events have no fees. The exact fee structure is shown during event creation.",
    category: "Payments",
  },
  {
    question: "How do I edit my event after publishing?",
    answer:
      "Navigate to your event page and click the edit button if you're the organizer. You can update the title, description, schedule, and other details. Note that some changes (like date) may trigger notifications to attendees.",
    category: "Events",
  },
  {
    question: "Can I get a receipt for my ticket purchase?",
    answer:
      'Yes, a receipt is automatically emailed to you after each purchase. You can also view and download receipts from your "My Tickets" page by selecting a ticket and clicking "View Receipt".',
    category: "Payments",
  },
  {
    question: "What happens if an event is cancelled?",
    answer:
      "If an organizer cancels an event, all ticket holders are automatically notified and refunds are processed within 5-10 business days. You'll receive an email with details about the refund.",
    category: "Events",
  },
  {
    question: "How do I check in at an event?",
    answer:
      'When you arrive at the event, show your ticket QR code from the "My Tickets" page to the event staff. They\'ll scan it to check you in. You can also use the mobile-friendly version of your ticket.',
    category: "Ticketing",
  },
];

const CATEGORY_META: {
  name: FaqCategory;
  icon: typeof TicketIcon;
  count: number;
}[] = [
  { name: "Ticketing", icon: TicketIcon, count: 12 },
  { name: "Events", icon: CalendarIcon, count: 8 },
  { name: "Payments", icon: CreditCardIcon, count: 6 },
];

const SIDEBAR_ITEMS = [
  "Getting Started",
  "FAQ",
  "Event Creation",
  "Ticket Management",
  "Payment Issues",
  "Contact Support",
] as const;

type SidebarSection = (typeof SIDEBAR_ITEMS)[number];

const CONTACT_SUBJECTS = [
  "Select a topic",
  "General Inquiry",
  "Ticketing Issue",
  "Payment Problem",
  "Event Creation Help",
  "Account Issue",
  "Bug Report",
  "Feature Request",
];

const FOOTER_LINKS = {
  Platform: ["Browse Events", "Create Events", "Pricing"],
  Support: ["Help Center", "Contact Us", "Community"],
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function HelpPage() {
  const [activeSection, setActiveSection] = useState<SidebarSection>("FAQ");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<FaqCategory | null>(
    null,
  );
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  // Contact form state
  const [contactSubject, setContactSubject] = useState(CONTACT_SUBJECTS[0]);
  const [contactEmail, setContactEmail] = useState("");
  const [contactMessage, setContactMessage] = useState("");
  const [contactFile, setContactFile] = useState<File | null>(null);
  const [contactSubmitting, setContactSubmitting] = useState(false);
  const [contactSuccess, setContactSuccess] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);

  const filteredFaqs = useMemo(() => {
    let items = FAQ_ITEMS;
    if (activeCategory) {
      items = items.filter((f) => f.category === activeCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      items = items.filter(
        (f) =>
          f.question.toLowerCase().includes(q) ||
          f.answer.toLowerCase().includes(q),
      );
    }
    return items;
  }, [activeCategory, searchQuery]);

  function toggleAccordion(index: number) {
    setExpandedIndex((prev) => (prev === index ? null : index));
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
  }

  async function handleContactSubmit(e: React.FormEvent) {
    e.preventDefault();
    setContactError(null);
    setContactSuccess(false);

    if (contactSubject === CONTACT_SUBJECTS[0]) {
      setContactError("Please select a topic.");
      return;
    }
    if (!contactEmail.trim()) {
      setContactError("Please enter your email.");
      return;
    }
    if (!contactMessage.trim()) {
      setContactError("Please enter a message.");
      return;
    }

    setContactSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("subject", contactSubject);
      formData.append("email", contactEmail);
      formData.append("message", contactMessage);
      if (contactFile) {
        formData.append("attachment", contactFile);
      }

      const res = await fetch(`${API_BASE}/contact/`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? "Failed to send message");
      }

      setContactSuccess(true);
      setContactSubject(CONTACT_SUBJECTS[0]);
      setContactEmail("");
      setContactMessage("");
      setContactFile(null);
    } catch (err) {
      setContactError(
        err instanceof Error ? err.message : "Something went wrong.",
      );
    } finally {
      setContactSubmitting(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setContactFile(file);
  }

  function handleSidebarClick(section: SidebarSection) {
    setActiveSection(section);
    if (section === "Contact Support") {
      document
        .getElementById("contact-support")
        ?.scrollIntoView({ behavior: "smooth" });
    } else if (section === "FAQ") {
      document
        .getElementById("faq-section")
        ?.scrollIntoView({ behavior: "smooth" });
    }
  }

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex gap-10">
          {/* Sidebar */}
          <aside className="hidden w-52 shrink-0 lg:block">
            <h2 className="text-lg font-semibold text-black">Help Center</h2>
            <nav className="mt-4">
              <ul className="space-y-1">
                {SIDEBAR_ITEMS.map((item) => (
                  <li key={item}>
                    <button
                      type="button"
                      onClick={() => handleSidebarClick(item)}
                      className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                        activeSection === item
                          ? "border-l-2 border-black bg-gray-50 font-medium text-black"
                          : "text-gray-600 hover:bg-gray-50 hover:text-black"
                      }`}
                    >
                      {item}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>

          {/* Main content */}
          <div className="min-w-0 flex-1">
            {/* FAQ Section */}
            <section id="faq-section">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <h1 className="text-2xl font-bold text-black">
                  Frequently Asked Questions
                </h1>
                <form
                  onSubmit={handleSearchSubmit}
                  className="flex items-stretch"
                >
                  <input
                    type="search"
                    placeholder="Search FAQ..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded-l-md border border-r-0 border-gray-300 bg-gray-50 px-3 py-2 text-sm placeholder:text-gray-500 focus:border-black focus:outline-none focus:ring-1 focus:ring-black sm:w-56"
                  />
                  <button
                    type="submit"
                    className="rounded-r-md bg-black px-3 py-2 text-white hover:bg-gray-800"
                  >
                    <SearchIcon className="h-4 w-4" />
                  </button>
                </form>
              </div>

              {/* Category tabs */}
              <div className="mt-8 flex flex-wrap gap-4">
                {CATEGORY_META.map((cat) => {
                  const Icon = cat.icon;
                  return (
                    <button
                      key={cat.name}
                      type="button"
                      onClick={() =>
                        setActiveCategory((c) =>
                          c === cat.name ? null : cat.name,
                        )
                      }
                      className={`flex min-w-[130px] flex-1 flex-col items-center gap-2 rounded-lg border px-6 py-5 transition-colors hover:border-gray-400 hover:bg-gray-50 ${
                        activeCategory === cat.name
                          ? "border-black bg-gray-50"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      <Icon className="h-6 w-6 text-gray-700" />
                      <span className="text-sm font-medium text-black">
                        {cat.name}
                      </span>
                      <span className="text-xs text-gray-500">
                        {cat.count} articles
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Accordion */}
              <div className="mt-8 divide-y divide-gray-200 border-t border-b border-gray-200">
                {filteredFaqs.length === 0 ? (
                  <p className="py-8 text-center text-gray-500">
                    No matching questions found.
                  </p>
                ) : (
                  filteredFaqs.map((faq, idx) => (
                    <div key={faq.question}>
                      <button
                        type="button"
                        onClick={() => toggleAccordion(idx)}
                        className="flex w-full items-center justify-between py-4 text-left text-sm font-medium text-black hover:text-gray-700"
                        aria-expanded={expandedIndex === idx}
                      >
                        <span>{faq.question}</span>
                        <ChevronDownIcon
                          className={`h-5 w-5 shrink-0 text-gray-400 transition-transform ${
                            expandedIndex === idx ? "rotate-180" : ""
                          }`}
                        />
                      </button>
                      {expandedIndex === idx && (
                        <div className="pb-4 pr-8 text-sm leading-relaxed text-gray-600">
                          {faq.answer}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* Contact Support Section */}
            <section id="contact-support" className="mt-16">
              <h2 className="text-2xl font-bold text-black">Contact Support</h2>

              <div className="mt-8 grid gap-10 lg:grid-cols-2">
                {/* Left: Contact info */}
                <div className="space-y-8">
                  <div className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100">
                      <EnvelopeIcon className="h-5 w-5 text-gray-700" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-black">
                        Email Support
                      </h3>
                      <p className="mt-1 text-sm text-gray-600">
                        Get help via email within 24 hours
                      </p>
                      <a
                        href="mailto:support@evently.com"
                        className="mt-1 text-sm font-medium text-black hover:underline"
                      >
                        support@evently.com
                      </a>
                    </div>
                  </div>

                  <div className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100">
                      <PhoneIcon className="h-5 w-5 text-gray-700" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-black">
                        Phone Support
                      </h3>
                      <p className="mt-1 text-sm text-gray-600">
                        Mon-Fri 9AM-6PM EST
                      </p>
                      <p className="mt-1 text-sm font-medium text-black">
                        1-800-123-4567
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100">
                      <ChatBubbleIcon className="h-5 w-5 text-gray-700" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-black">Live Chat</h3>
                      <p className="mt-1 text-sm text-gray-600">
                        Available 24/7 for urgent issues
                      </p>
                      <button
                        type="button"
                        className="mt-2 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-black hover:bg-gray-50"
                      >
                        Start Chat
                      </button>
                    </div>
                  </div>
                </div>

                {/* Right: Contact form */}
                <form onSubmit={handleContactSubmit} className="space-y-4">
                  {contactSuccess && (
                    <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                      Message sent successfully! We&apos;ll get back to you
                      soon.
                    </div>
                  )}
                  {contactError && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      {contactError}
                    </div>
                  )}

                  <div>
                    <label
                      htmlFor="contact-subject"
                      className="block text-sm font-medium text-black"
                    >
                      Subject
                    </label>
                    <select
                      id="contact-subject"
                      value={contactSubject}
                      onChange={(e) => setContactSubject(e.target.value)}
                      className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-black focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
                    >
                      {CONTACT_SUBJECTS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="contact-email"
                      className="block text-sm font-medium text-black"
                    >
                      Email
                    </label>
                    <input
                      id="contact-email"
                      type="email"
                      placeholder="your@email.com"
                      value={contactEmail}
                      onChange={(e) => setContactEmail(e.target.value)}
                      className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="contact-message"
                      className="block text-sm font-medium text-black"
                    >
                      Message
                    </label>
                    <textarea
                      id="contact-message"
                      rows={4}
                      placeholder="Describe your issue..."
                      value={contactMessage}
                      onChange={(e) => setContactMessage(e.target.value)}
                      className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-black">
                      Attachment (optional)
                    </label>
                    <label
                      htmlFor="contact-file"
                      className="mt-1 flex cursor-pointer flex-col items-center gap-2 rounded-md border-2 border-dashed border-gray-300 px-4 py-6 text-center transition-colors hover:border-gray-400"
                    >
                      <UploadIcon className="h-8 w-8 text-gray-400" />
                      <span className="text-sm text-gray-500">
                        {contactFile
                          ? contactFile.name
                          : "Drop files here or click to upload"}
                      </span>
                      <input
                        id="contact-file"
                        type="file"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={contactSubmitting}
                    className="w-full rounded-md bg-black px-6 py-3 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
                  >
                    {contactSubmitting ? "Sending…" : "Send Message"}
                  </button>
                </form>
              </div>
            </section>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-gray-200 bg-white py-12 text-gray-600">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded bg-black text-white text-sm font-bold">
                  E
                </span>
                <span className="text-lg font-semibold text-black">
                  Evently
                </span>
              </div>
              <p className="mt-3 text-sm text-gray-500">
                The world&apos;s largest event technology platform.
              </p>
            </div>
            {Object.entries(FOOTER_LINKS).map(([heading, links]) => (
              <div key={heading}>
                <h4 className="font-semibold text-black">{heading}</h4>
                <ul className="mt-4 space-y-2">
                  {links.map((link) => (
                    <li key={link}>
                      <a
                        href={
                          link === "Browse Events"
                            ? "/"
                            : link === "Create Events"
                              ? "/create"
                              : link === "Help Center"
                                ? "/help"
                                : "#"
                        }
                        className="text-sm hover:text-black"
                      >
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <div>
              <h4 className="font-semibold text-black">Connect</h4>
              <div className="mt-4 flex gap-4">
                {["Facebook", "Twitter", "Instagram"].map((name) => (
                  <a
                    key={name}
                    href="#"
                    className="text-sm hover:text-black"
                    aria-label={name}
                  >
                    {name === "Facebook" ? "f" : name === "Twitter" ? "𝕏" : "◉"}
                  </a>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-12 border-t border-gray-200 pt-8 text-center">
            <p className="text-sm text-gray-500">
              © 2025 Evently. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
