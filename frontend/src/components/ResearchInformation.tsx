/**
 * Research information panel.
 * Explains study consent and participation details.
 */

export default function ResearchInformation({
  className = "",
}: {
  className?: string;
}) {
  return (
    <section
      className={className}
      aria-labelledby="research-info-title"
    >
      <h3 id="research-info-title" className="text-base font-bold leading-snug mt-0 mb-3">
        Research Information
      </h3>
      <p className="mt-0 mb-3">
        An AI Orchestration System for Translating Visual Brand Cues into
        Cross-Sensory Brand Experience
      </p>
      <p className="mb-3">
        Thank you for your interest in this research project. Your participation
        is very much appreciated. This Participant Information Sheet explains
        what will happen if you choose to take part in this evaluation study.
      </p>

      <h4 className="font-bold mt-4 mb-1">What is the evaluation for?</h4>
      <p className="mb-3">
        This evaluation studies Brandbit, an AI orchestration system that takes
        a brand image and generates a cross-sensory brand concept (fragrance
        direction, music direction, and a short rationale). The aim is to
        understand whether people judge those outputs as coherent with the
        source image, including a comparison between a structured Brand
        Aesthetic Descriptor (BAD) process and a prompt-only process.
      </p>

      <h4 className="font-bold mt-4 mb-1">
        What will I be asked to do if I participate?
      </h4>
      <p className="mb-3">
        You will sign in with Google, view one or more generated brand concepts
        (image, fragrance notes, and music/audio), answer brief background
        questions about prior experience in perfumery, music, and creative
        design, and rate each concept on a 1–5 scale. Optional comments are
        welcome. You may stop at any time.
      </p>

      <h4 className="font-bold mt-4 mb-1">
        What will happen to the information I provide?
      </h4>
      <p className="mb-2">The evaluation may be used in:</p>
      <p className="mb-1">
        (i) the researcher&apos;s final-year project report and related
        academic assessment;
      </p>
      <p className="mb-3">
        (ii) demonstration of the prototype to supervisors or examiners.
      </p>
      <p className="mb-3">
        Ratings and comments will be reported anonymously. You will not be
        referred to by name, place of work, or job title in the project report
        or related materials.
      </p>
      <p className="mb-3">
        Sign-in uses your Google account so the study can save your session and
        ratings, and so you can later ask for your data to be withdrawn. That
        means the researcher can link a rating to an account. It is{" "}
        <span className="font-bold">not fully anonymous to the researcher</span>
        . In the project report and related materials, ratings and comments are
        still presented without your name, email, workplace, or job title.
      </p>
      <p className="mb-3">
        Your Google account information (your “personal data”) will be stored
        securely by the principal project researcher and will not be published
        as an identifier in the report.
      </p>
      <p className="mb-3">
        Your data will be held for up to six months after the end of the
        project (expected March 2027), and then securely destroyed. You can
        request a copy of your data at any time before this date.
      </p>

      <h4 className="font-bold mt-4 mb-1">
        What if I have any questions relating to my data or want to withdraw my
        personal data?
      </h4>
      <p className="mb-3">
        You can send any questions relating to the processing of your data or
        request to withdraw your personal data by contacting me{" "}
        <a
          href="mailto:ac531@london.ac.uk"
          className="font-bold underline decoration-gold underline-offset-2"
        >
          ac531@student.london.ac.uk
        </a>
        .
      </p>
      <p className="mb-3">
        If you have any concerns about the processing of your personal data or
        your information rights, please see the University’s data protection
        web pages. Or contact the Data Protection Officer:{" "}
        <a
          href="mailto:dp@gold.ac.uk"
          className="font-bold underline decoration-gold underline-offset-2"
        >
          dp@gold.ac.uk
        </a>
        .
      </p>
      <p className="mb-3">
        You can also contact the Information Commissioners’ Office —{" "}
        <a
          href="https://ico.org.uk"
          target="_blank"
          rel="noopener noreferrer"
          className="font-bold underline decoration-gold underline-offset-2"
        >
          https://ico.org.uk
        </a>{" "}
        — in relation to any concerns or issue you may have with the processing
        of your personal information.
      </p>

      <h4 className="font-bold mt-4 mb-1">Declaration by researcher</h4>
      <p className="mb-3">
        I have provided the above participant with this Participant Information
        Sheet, given the participant the opportunity to ask further questions,
        and believe that the participant has understood the process.
      </p>
      <p className="mb-1">
        Name of the researcher:{" "}
        <span className="font-bold">Alexander Chua</span>
      </p>
      <p className="mb-0">Date (DD/MM/YYYY): 01/09/2026</p>
    </section>
  );
}
