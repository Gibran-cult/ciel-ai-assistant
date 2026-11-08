import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import Story from "@/components/Story";
import FakeJournal from "@/components/FakeJournal";
import Legend from "@/components/Legend";
import Pricing from "@/components/Pricing";
import Faq from "@/components/Faq";
import Closing from "@/components/Closing";
import Footer from "@/components/Footer";
import RobotLayer from "@/components/RobotLayer";
import Motion from "@/components/Motion";

export default function Page() {
  return (
    <div id="atas" className="relative overflow-x-clip">
      <a className="skip-link" href="#isi">
        Langsung ke isi
      </a>

      {/* The hero's still bust (RobotBust) is the LCP; this layer replaces it once its first frame is drawn. */}
      <RobotLayer />
      <Motion />

      <Nav />
      <main id="isi" tabIndex={-1} className="relative z-[1] outline-none">
        <Hero />
        <Story />
        <FakeJournal />
        <Legend />
        <Pricing />
        <Faq />
        <Closing />
      </main>
      <Footer />
    </div>
  );
}
