"""
Train a balanced multilingual Subject Classifier using scikit-learn.
Balanced across: Physics, Chemistry, Biology, Mathematics.
Equally represented in English, Telugu, Hindi, and Mixed/Transliterated.
"""

import json
import os
import sys
from pathlib import Path
from collections import Counter
import joblib

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.linear_model import LogisticRegression

MODEL_PATH = api_dir / "app" / "src" / "modules" / "tutor" / "subject_classifier.joblib"

# Comprehensive balanced subject corpora
CURRICULUM_DATA = {
    "physics": {
        "en": [
            "Newton's laws of motion", "first law of motion and inertia", "second law of motion F=ma",
            "third law of motion action and reaction", "momentum and conservation of linear momentum",
            "impulse and force-time relationship", "friction static friction kinetic friction rolling friction",
            "universal law of gravitation", "gravitational constant G and acceleration due to gravity g",
            "orbital velocity and escape velocity", "Kepler's laws of planetary motion",
            "work done by a constant force and variable force", "kinetic energy and potential energy",
            "work-energy theorem", "power and efficiency", "conservation of mechanical energy",
            "rotational motion and moment of inertia", "torque and angular momentum", "center of mass",
            "oscillations and simple harmonic motion SHM", "simple pendulum time period formula",
            "waves sound waves transverse waves longitudinal waves", "frequency wavelength and wave velocity",
            "reflection of light and spherical mirrors", "refraction of light and Snell's law",
            "refractive index and critical angle", "total internal reflection and optical fibers",
            "dispersion of light through a prism", "thin lenses lens maker formula lens formula",
            "electrostatics electric charge and Coulomb's law", "electric field and electric dipole",
            "Gauss's law and flux", "electrostatic potential and capacitance", "capacitors in series and parallel",
            "current electricity Ohm's law V=IR", "resistance and resistivity", "resistors in series and parallel",
            "Kirchhoff's laws junction rule and loop rule", "electric power and heating effect of electric current",
            "magnetic field Biot-Savart law and Ampere's circuital law", "force on moving charge Lorentz force",
            "electromagnetic induction Faraday's laws and Lenz's law", "alternating current AC generator and transformer",
            "electromagnetic waves", "photoelectric effect and Einstein's equation", "Bohr model of hydrogen atom",
            "radioactivity and nuclear fission fusion", "semiconductors diodes rectifiers",
            "kinematics equations v=u+at s=ut+1/2at^2 v^2=u^2+2as", "vectors projectile motion trajectory",
            "pressure in fluids Pascal's law Archimedes principle buoyancy", "viscosity and terminal velocity",
            "Bernoulli's principle and equation", "surface tension and capillarity",
            "thermal expansion specific heat capacity latent heat", "thermodynamics first law and second law heat engines"
        ],
        "te": [
            "న్యూటన్ గమన నియమాలు", "మొదటి గమన నియమం మరియు జడత్వం", "రెండవ గమన నియమం సూత్రం F=ma",
            "మూడవ గమన నియమం చర్య మరియు ప్రతిచర్య", "ద్రవ్యవేగం మరియు ద్రవ్యవేగ నిత్యత్వ నియమం",
            "ప్రచోదనం మరియు బలం", "ఘర్షణ స్థైతిక ఘర్షణ గతిక ఘర్షణ దొర్లు ఘర్షణ",
            "సార్వత్రిక గురుత్వాకర్షణ నియమం", "గురుత్వాకర్షణ స్థిరాంకం G మరియు గురుత్వ త్వరణం g",
            "కక్ష్యా వేగం మరియు పలాయన వేగం", "కెప్లర్ గ్రహ గమన నియమాలు",
            "పని, గతిజ శక్తి మరియు స్థితిజ శక్తి", "పని-శక్తి సిద్ధాంతం", "సామర్థ్యం",
            "యాంత్రిక శక్తి నిత్యత్వ నియమం", "భ్రమణ గమనం మరియు జడత్వ భ్రామకం", "టార్క్ మరియు కోణీయ ద్రవ్యవేగం",
            "ద్రవ్యరాశి కేంద్రం", "డోలనాలు మరియు సరళ హరాత్మక చలనం SHM", "సరళ లోలకం డోలన కాలం సూత్రం",
            "ధ్వని తరంగాలు తిర్యక్ తరంగాలు అనుదైర్ఘ్య తరంగాలు", "పౌనఃపున్యం తరంగదైర్ఘ్యం మరియు తరంగ వేగం",
            "కాంతి పరావర్తనం మరియు గోళాకార దర్పణాలు", "కాంతి వక్రీభవనం మరియు స్నెల్ నియమం",
            "వక్రీభవన గుణకం మరియు సందిగ్ధ కోణం", "సంపూర్ణాంతర పరావర్తనం మరియు ఆప్టికల్ ఫైబర్",
            "పట్టకం ద్వారా కాంతి విక్షేపణం", "కటకాలు కటక సూత్రం",
            "స్థిర విద్యుత్ విద్యుత్ ఆవేశాలు మరియు కూలూమ్ నియమం", "విద్యుత్ క్షేత్రం మరియు విద్యుత్ డైపోల్",
            "గాస్ నియమం", "విద్యుత్ పొటెన్షియల్ మరియు కెపాసిటెన్స్",
            "విద్యుత్ ప్రవాహం ఓమ్ నియమం V=IR", "విద్యుత్ నిరోధం మరియు విశిష్ట నిరోధం", "శ్రేణి మరియు సమాంతర సంధానం",
            "కిర్చాఫ్ నియమాలు", "విద్యుత్ సామర్థ్యం మరియు జౌల్ ఉష్ణ నియమం",
            "అయస్కాంత క్షేత్రం మరియు బయోట్-సావర్ట్ నియమం", "ఆంపియర్ నియమం లారెంజ్ బలం",
            "విద్యుదయస్కాంత ప్రేరణ ఫారడే నియమాలు లెంజ్ నియమం", "ఏకాంతర విద్యుత్ AC మరియు ట్రాన్స్‌ఫార్మర్",
            "విద్యుదయస్కాంత తరంగాలు", "కాంతి విద్యుత్ ఫలితం", "బోర్ పరమాణు నమూనా",
            "రేడియోధార్మికత మరియు కేంద్రక విచ్ఛిత్తి", "అర్ధవాహకాలు డయోడ్",
            "చలన సమీకరణాలు ప్రక్షేపక గమనం", "ద్రవాల పీడనం పాస్కల్ నియమం ఆర్కిమెడిస్ సూత్రం ప్లవన సూత్రం",
            "స్నిగ్ధత మరియు అంతిమ వేగం", "బెర్నౌలీ సిద్ధాంతం", "తలతన్యత మరియు కేశనాళికీయత",
            "ఉష్ణ విస్తరణ విశిష్టోష్ణం గుప్తోష్ణం", "ఉష్ణగతిక శాస్త్రం మొదటి మరియు రెండవ నియమం"
        ],
        "hi": [
            "न्यूटन के गति के नियम", "गति का प्रथम नियम और जड़त्व", "गति का द्वितीय नियम सूत्र F=ma",
            "गति का तृतीय नियम क्रिया और प्रतिक्रिया", "संवेग और संवेग संरक्षण का नियम",
            "आवेग और बल", "घर्षण स्थैतिक घर्षण गतिक घर्षण लोटनिक घर्षण",
            "सार्वत्रिक गुरुत्वाकर्षण का नियम", "गुरुत्वाकर्षण स्थिरांक G और गुरुत्वीय त्वरण g",
            "कक्षीय वेग और पलायन वेग", "केप्लर के ग्रहीय गति के नियम",
            "कार्य गतिज ऊर्जा और स्थितिज ऊर्जा", "कार्य-ऊर्जा प्रमेय", "शक्ति और दक्षता",
            "यांत्रिक ऊर्जा संरक्षण का नियम", "घूर्णी गति और जड़त्व आघूर्ण", "बल आघूर्ण और कोणीय संवेग",
            "द्रव्यमान केंद्र", "दोलन और सरल आवर्त गति SHM", "सरल लोलक का आवर्तकाल सूत्र",
            "ध्वनि तरंगें अनुप्रस्थ तरंगें अनुदैर्ध्य तरंगें", "आवृत्ति तरंगदैर्घ्य और तरंग वेग",
            "प्रकाश का परावर्तन और गोलीय दर्पण", "प्रकाश का अपवर्तन और स्नेल का नियम",
            "अपवर्तनांक और क्रांतिक कोण", "पूर्ण आंतरिक परावर्तन और ऑप्टिकल फाइबर",
            "प्रिज्म द्वारा प्रकाश का विक्षेपण", "लेंस और लेंस सूत्र",
            "स्थिरवैद्युतिकी विद्युत आवेश और कूलॉम का नियम", "विद्युत क्षेत्र और विद्युत द्विध्रुव",
            "गाउस का नियम", "विद्युत विभव और धारिता",
            "विद्युत धारा ओम का नियम V=IR", "प्रतिरोध और प्रतिरोधकता", "श्रेणीक्रम और समांतरक्रम संयोजन",
            "किरचॉफ के नियम", "विद्युत शक्ति और जूल का तापन नियम",
            "चुंबकीय क्षेत्र बायो-सावर्ट नियम", "ऐम्पियर का नियम लॉरेंट्ज़ बल",
            "वैद्युतचुंबकीय प्रेरण फैराडे के नियम लेन्ज़ का नियम", "प्रत्यावर्ती धारा AC और ट्रांसफॉर्मर",
            "वैद्युतचुंबकीय तरंगें", "प्रकाश विद्युत प्रभाव", "बोहर का परमाणु मॉडल",
            "रेडियोधर्मिता और नाभिकीय विखंडन", "अर्धचालक डायोड",
            "गति के समीकरण प्रक्षेप्य गति", "तरल दाब पास्कल का नियम आर्किमिडीज का सिद्धांत उत्प्लावन",
            "श्यानता और सीमांत वेग", "बरनौली का सिद्धांत", "पृष्ठ तनाव और केशिकत्व",
            "तापीय प्रसार विशिष्ट ऊष्मा धारिता गुप्त ऊष्मा", "ऊष्मागतिकी का प्रथम और द्वितीय नियम"
        ]
    },
    "chemistry": {
        "en": [
            "chemical reactions and chemical equations", "balancing chemical equations",
            "combination reaction decomposition reaction displacement reaction double displacement reaction",
            "oxidation and reduction redox reactions", "oxidizing agent and reducing agent",
            "exothermic and endothermic reactions", "acids bases and salts indicators litmus paper",
            "pH scale acid rain neutralization reaction", "metals and non-metals physical and chemical properties",
            "reactivity series of metals metallurgy extraction of metals", "corrosion and prevention of corrosion",
            "carbon and its compounds covalent bonding in carbon", "allotropes of carbon diamond graphite fullerenes",
            "versatile nature of carbon catenation tetravalency", "hydrocarbons saturated and unsaturated hydrocarbons",
            "alkanes alkenes alkynes homologous series", "functional groups alcohols aldehydes ketones carboxylic acids",
            "nomenclature of carbon compounds IUPAC naming", "combustion oxidation addition substitution reactions of carbon",
            "ethanol and ethanoic acid properties and reactions", "soaps and detergents micelle formation",
            "periodic table classification of elements Mendeleev periodic table modern periodic law",
            "groups and periods in periodic table periodic trends valency atomic size ionization energy electronegativity",
            "structure of atom Thomson model Rutherford model Bohr model", "subatomic particles electron proton neutron",
            "atomic number mass number isotopes isobars", "electronic configuration valence electrons octet rule",
            "chemical bonding ionic bond electrovalent bond covalent bond coordinate bond",
            "Lewis dot structures formal charge", "polar and non-polar covalent bonds dipole moment",
            "states of matter solid liquid gas intermolecular forces", "Boyle's law Charles law Gay-Lussac law Avogadro law ideal gas equation PV=nRT",
            "Dalton's law of partial pressures Graham's law of diffusion", "chemical thermodynamics enthalpy internal energy entropy Gibbs free energy",
            "chemical equilibrium dynamic equilibrium law of chemical equilibrium equilibrium constant Kc Kp",
            "Le Chatelier's principle factors affecting equilibrium", "solutions molarity molality mole fraction normality solubility",
            "electrochemistry galvanic cell electrolytic cell Nernst equation standard electrode potential",
            "chemical kinetics rate of reaction order of reaction rate constant half-life period",
            "surface chemistry adsorption catalysis catalysts enzymes", "coordination compounds ligands coordination number isomers"
        ],
        "te": [
            "రసాయన చర్యలు మరియు రసాయన సమీకరణాలు", "రసాయన సమీకరణాలను తుల్యం చేయడం",
            "సంయోగ చర్య వియోగ చర్య స్థానభ్రంశ చర్య ద్వంద్వ స్థానభ్రంశ చర్య",
            "ఆక్సీకరణం మరియు క్షయకరణం రెడాక్స్ చర్యలు", "ఆక్సీకరణ కారకం క్షయకరణ కారకం",
            "ఉష్ణమోచక మరియు ఉష్ణగ్రాహక చర్యలు", "ఆమ్లాలు క్షారాలు మరియు లవణాలు సూచికలు లిట్మస్",
            "pH స్కేల్ తటస్థీకరణ చర్య ఆమ్ల వర్షం", "లోహాలు మరియు అలోహాలు భౌతిక రసాయన ధర్మాలు",
            "లోహాల చర్యాశీలత శ్రేణి లోహ సంగ్రహణం", "తుప్పు పట్టడం మరియు నివారణ",
            "కార్బన్ మరియు దాని సమ్మేళనాలు సమయోజనీయ బంధం", "కార్బన్ రూపాంతరాలు వజ్రం గ్రాఫైట్ పుల్లరీన్",
            "కాటనేషన్ చతుర్సంయోజకత", "హైడ్రోకార్బన్లు సంతృప్త మరియు అసంతృప్త హైడ్రోకార్బన్లు",
            "ఆల్కేన్లు ఆల్కీన్లు ఆల్కైన్లు సమజాత శ్రేణి", "ప్రమేయ సమూహాలు ఆల్కహాల్ ఆల్డిహైడ్ కీటోన్ కార్బాక్సిలిక్ ఆమ్లం",
            "IUPAC నామకరణం కర్బన సమ్మేళనాలు", "దహనం ఆక్సీకరణ సంకలన ప్రతిక్షేపణ చర్యలు",
            "ఇథనాల్ మరియు ఇథనోయిక్ ఆమ్లం ధర్మాలు", "సబ్బులు మరియు డిటర్జెంట్లు మిసెల్",
            "ఆవర్తన పట్టిక మూలకాల వర్గీకరణ మెండలీవ్ ఆవర్తన పట్టిక ఆధునిక ఆవర్తన నియమం",
            "గ్రూపులు మరియు పీరియడ్లు పరమాణు పరిమాణం అయనీకరణ శక్తి రుణవిద్యుదాత్మకత",
            "పరమాణు నిర్మాణం థామ్సన్ నమూనా రూథర్‌ఫర్డ్ నమూనా బోర్ నమూనా", "ఎలక్ట్రాన్ ప్రోటాన్ న్యూట్రాన్",
            "పరమాణు సంఖ్య ద్రవ్యరాశి సంఖ్య ఐసోటోపులు ఐసోబార్లు", "ఎలక్ట్రాన్ విన్యాసం వేలన్సీ అష్టక నియమం",
            "రసాయన బంధం అయానిక బంధం సమయోజనీయ బంధం సంయోజనీయత", "లూయిస్ బిందు నిర్మాణం ద్విధ్రువ భ్రామకం",
            "పదార్థ స్థితులు ఘన ద్రవ వాయు అంతరణుక బలాలు", "బాయిల్ నియమం చార్లెస్ నియమం ఆదర్శ వాయు సమీకరణం PV=nRT",
            "రసాయన ఉష్ణగతిక శాస్త్రం ఎంథాల్పీ ఎంట్రోపీ గిబ్స్ స్వేచ్ఛా శక్తి", "రసాయన సమతాస్థితి సమతాస్థితి స్థిరాంకం Kc Kp లీ చాట్లియర్ సూత్రం",
            "ద్రావణాలు మొలారిటీ మొలాలిటీ మోల్ భాగం ద్రావణీయత", "విద్యుత్ రసాయన శాస్త్రం గాల్వానిక్ ఘటం నెర్న్‌స్ట్ సమీకరణం",
            "రసాయన గతిశాస్త్రం చర్య వేగం వేగ స్థిరాంకం అర్ధ జీవిత కాలం", "ఉత్ప్రేరకం ఉత్ప్రేరకాలు ఎంజైములు సమన్వయ సమ్మేళనాలు",
            "మోల్ భావన మరియు అవగాడ్రో సంఖ్య"
        ],
        "hi": [
            "रासायनिक अभिक्रियाएं एवं समीकरण", "रासायनिक समीकरण को संतुलित करना",
            "संयोजन अभिक्रिया वियोजन अभिक्रिया विस्थापन अभिक्रिया द्विविस्थापन अभिक्रिया",
            "उपचयन और अपचयन रेडॉक्स अभिक्रियाएं", "ऑक्सीकारक और अपचायक",
            "ऊष्माक्षेपी और ऊष्माशोषी अभिक्रियाएं", "अम्ल क्षारक एवं लवण सूचक लिटमस पत्र",
            "pH पैमाना उदासीनीकरण अभिक्रिया अम्लीय वर्षा", "धातु एवं अधातु भौतिक और रासायनिक गुण",
            "सक्रियता श्रेणी धातुकर्म धातु निष्कर्षण", "संक्षारण और संक्षारण से सुरक्षा",
            "कार्बन एवं उसके यौगिक सहसंयोजी आबंधन", "कार्बन के अपररूप हीरा ग्रेफाइट फुलरीन",
            "शृंखलन चतुःसंयोजकता", "हाइड्रोकार्बन संतृप्त और असंतृप्त हाइड्रोकार्बन",
            "एल्केन एल्कीन एल्काइन समजातीय श्रेणी", "प्रकार्यात्मक समूह एल्कोहॉल एल्डिहाइड कीटोन कार्बोक्सिलिक अम्ल",
            "IUPAC नामकरण कार्बनिक यौगिक", "दहन ऑक्सीकरण संकलन प्रतिस्थापन अभिक्रियाएं",
            "एथेनॉल और एथेनोइक अम्ल के गुणधर्म", "साबुन और अपमार्जक मिसेल निर्माण",
            "तत्वों का आवर्त वर्गीकरण मेंडेलीव की आवर्त सारणी आधुनिक आवर्त नियम",
            "समूह और आवर्त परमाणु त्रिज्या आयनन एन्थैल्पी विद्युत ऋणात्मकता",
            "परमाणु की संरचना थॉमसन मॉडल रदरफोर्ड मॉडल बोहर मॉडल", "इलेक्ट्रॉन प्रोटॉन न्यूट्रॉन",
            "परमाणु क्रमांक द्रव्यमान संख्या समस्थानिक समभारिक", "इलेक्ट्रॉनिक विन्यास संयोजकता अष्टक नियम",
            "रासायनिक आबंधन आयनिक आबंध सहसंयोजक आबंध", "लुईस बिंदु संरचना द्विध्रुव आघूर्ण",
            "द्रव्य की अवस्थाएं ठोस द्रव गैस अंतराआण्विक बल", "बॉयल का नियम चार्ल्स का नियम आदर्श गैस समीकरण PV=nRT",
            "रासायनिक ऊष्मागतिकी एन्थैल्पी एन्ट्रॉपी गिब्स मुक्त ऊर्जा", "रासायनिक साम्यावस्था साम्य स्थिरांक ला शातेलिए का सिद्धांत",
            "विलयन मोलरता मोललता मोल अंश विलेयता", "विद्युत रसायन गैल्वेनिक सेल नेर्नस्ट समीकरण",
            "रासायनिक बलगतिकी अभिक्रिया का वेग वेग स्थिरांक अर्धायु काल", "उत्प्रेरक उत्प्रेरण समन्वय यौगिक",
            "मोल संकल्पना और आवोगाद्रो संख्या"
        ]
    },
    "biology": {
        "en": [
            "life processes in living organisms", "nutrition autotrophic nutrition and heterotrophic nutrition",
            "photosynthesis light reaction dark reaction Calvin cycle chlorophyll chloroplast thylakoid",
            "stomata opening and closing mechanism transpiration", "digestion and digestive system enzymes pepsin trypsin salivary amylase",
            "respiration aerobic respiration and anaerobic respiration glycolysis Krebs cycle ATP mitochondria",
            "human respiratory system lungs alveoli exchange of gases", "transportation in human beings circulatory system heart blood vessels",
            "structure of human heart double circulation cardiac cycle arteries veins capillaries hemoglobin",
            "transport in plants xylem and phloem transport of water and food translocation",
            "excretion and excretory system human kidney nephron urine formation dialysis",
            "control and coordination nervous system neuron structure synapse reflex arc brain spinal cord",
            "endocrine system endocrine glands hormones pituitary thyroid adrenaline insulin pancreas",
            "how do organisms reproduce asexual reproduction fission budding regeneration spore formation vegetative propagation",
            "sexual reproduction in flowering plants flower structure pollination fertilization ovary ovule seed formation",
            "reproduction in human beings male and female reproductive systems menstrual cycle fertilization embryo development",
            "heredity and variation Mendel's laws of inheritance monohybrid cross dihybrid cross alleles genes",
            "dominant trait and recessive trait genotype and phenotype Punnett square sex determination in humans",
            "molecular basis of inheritance DNA structure double helix nucleotide replication RNA transcription translation",
            "evolution theory of natural selection Darwin adaptation speciation homologous and analogous organs fossils",
            "our environment ecosystem food chain food web trophic levels 10 percent law biomagnification ozone layer",
            "management of natural resources conservation of forests wildlife water harvesting",
            "cell the unit of life cell theory Robert Hooke Schwann Schleiden Virchow",
            "prokaryotic cell and eukaryotic cell differences plant cell vs animal cell",
            "cell organelles nucleus chromatin endoplasmic reticulum Golgi apparatus lysosomes vacuoles ribosomes",
            "cell cycle and cell division mitosis and meiosis phases of cell division",
            "biomolecules carbohydrates proteins lipids amino acids enzymes nucleic acids",
            "plant kingdom algae bryophytes pteridophytes gymnosperms angiosperms",
            "animal kingdom non-chordates chordates vertebrates invertebrates classification",
            "human health and disease immunity innate immunity acquired immunity vaccines antibodies pathogens AIDS cancer",
            "cell theory Robert Hooke Schwann Schleiden Virchow who proposed cell theory",
            "Mendel's laws of inheritance and variation monohybrid cross dihybrid cross"
        ],
        "te": [
            "జీవులలో జీవ క్రియలు", "పోషణ స్వయంపోషణ మరియు పరపోషణ",
            "కణ సిద్ధాంతం మరియు దానిని ఎవరు ప్రతిపాదించారు రాబర్ట్ హుక్ ష్వాన్ ష్లీడెన్",
            "మెండల్ అనువంశికత సూత్రాలు మరియు ఏక సంకర సంకరణం జన్యుశాస్త్రం",
            "కిరణజన్య సంయోగక్రియ కాంతి చర్య నిష్కాంతి చర్య హరితరేణువు క్లోరోఫిల్ థైలకాయిడ్",
            "పత్రరంధ్రాలు తెరుచుకోవడం మరియు మూసుకోవడం భాష్పోత్సేకం", "జీర్ణవ్యవస్థ మరియు జీర్ణక్రియ ఎంజైములు పెప్సిన్ ట్రిప్సిన్ ఎమైలేజ్",
            "శ్వాసక్రియ వాయు సహిత శ్వాసక్రియ అవాయు శ్వాసక్రియ గ్లైకాలసిస్ క్రెబ్స్ వలయం ATP మైటోకాండ్రియా",
            "మానవ శ్వాసకోశ వ్యవస్థ ఊపిరితిత్తులు వాయుకోశ గోణులు వాయు మార్పిడి", "రక్త ప్రసరణ వ్యవస్థ మానవ గుండె రక్త నాళాలు",
            "గుండె నిర్మాణం ద్వంద్వ ప్రసరణ ధమనులు సిరలు రక్త కేశనాళికలు హిమోగ్లోబిన్",
            "మొక్కలలో రవాణా దారువు మరియు పోషక కణజాలం నీరు మరియు ఆహార రవాణా",
            "విసర్జక వ్యవస్థ మానవ మూత్రపిండాలు నెఫ్రాన్ మూత్రం ఏర్పడటం డయాలసిస్",
            "నియంత్రణ మరియు సమన్వయం నాడీ వ్యవస్థ న్యూరాన్ సైనాప్స్ ప్రతిక్రియ చాపం మెదడు వెన్నుపాము",
            "అంతఃస్రావక వ్యవస్థ హార్మోన్లు పిట్యూటరీ థైరాయిడ్ అడ్రినలిన్ ఇన్సులిన్ క్లోమం",
            "జీవులు ఎలా ప్రత్యుత్పత్తి జరుపుతాయి అలైంగిక ప్రత్యుత్పత్తి విచ్ఛిత్తి కోరకీభవనం సిద్ధబీజాలు శాఖీయ ప్రత్యుత్పత్తి",
            "పుష్పించే మొక్కలలో లైంగిక ప్రత్యుత్పత్తి పరాగసంపర్కం ఫలదీకరణం అండాశయం విత్తనం",
            "మానవ ప్రత్యుత్పత్తి స్త్రీ పురుష ప్రత్యుత్పత్తి వ్యవస్థలు రుతుచక్రం పిండం అభివృద్ధి",
            "అనువంశికత మరియు వైవిధ్యం మెండల్ అనువంశికత సూత్రాలు ఏక సంకర సంకరణం యుగ్మవికల్పాలు జన్యువులు",
            "బహిర్గత అంతర్గత లక్షణాలు జన్యురూపం దృశ్యరూపం మానవులలో లింగ నిర్ధారణ",
            "డీఎన్‌ఏ నిర్మాణం ద్వంద్వ కుండలి న్యూక్లియోటైడ్ ప్రతికృతి ఆర్‌ఎన్‌ఏ ట్రాన్స్‌క్రిప్షన్",
            "జీవ పరిణామం డార్విన్ సహజ ఎంపిక అనుకూలనాలు సమజాత అవయవాలు శిలాజాలు",
            "పర్యావరణం జీవావరణ వ్యవస్థ ఆహారపు గొలుసు ఆహార జాలకం పోషక స్థాయిలు జీవవర్ధనం ఓజోన్ పొర",
            "కణం జీవ ప్రమాణం కణ సిద్ధాంతం రాబర్ట్ హుక్ ష్వాన్ ష్లీడెన్ విర్చో",
            "కేంద్రకపూర్వ కణం నిజకేంద్రక కణం వృక్ష కణం జంతు కణం తేడాలు",
            "కణాంగాలు కేంద్రకం ఎండోప్లాస్మిక్ రెటిక్యులం గాల్జీ సంక్లిష్టం లైసోసోములు రిబోసోములు",
            "కణ విభజన సమవిభజన మరియు క్షయకరణ విభజన", "జీవ అణువులు ప్రోటీన్లు న్యూక్లియిక్ ఆమ్లాలు ఎంజైములు",
            "వృక్ష సామ్రాజ్యం మరియు జంతు సామ్రాజ్యం వర్గీకరణ వెన్నెముక గలవి లేనివి",
            "మానవ ఆరోగ్యం మరియు వ్యాధులు రోగనిరోధక శక్తి వ్యాక్సిన్లు యాంటీబాడీలు ఎయిడ్స్ క్యాన్సర్"
        ],
        "hi": [
            "जीव प्रक्रम सजीवों में जीवन की प्रक्रियाएं", "पोषण स्वपोषी पोषण और विषमपोषी पोषण",
            "प्रकाश संश्लेषण प्रकाशिक अभिक्रिया अप्रकाशिक अभिक्रिया क्लोरोफिल हरितलवक थाइलाकोइड",
            "रंध्र खुलने और बंद होने की क्रियाविधि वाष्पोत्सर्जन", "पाचन तंत्र एंजाइम पेप्सिन ट्रिप्सिन एमाइलेज",
            "श्वसन वायवीय श्वसन और अवायवीय श्वसन ग्लाइकोलाइसिस क्रेब्स चक्र एटीपी माइटोकॉन्ड्रिया",
            "मानव श्वसन तंत्र फेफड़े कूपिकाएं गैसों का विनिमय", "परिसंचरण तंत्र मानव हृदय रक्त वाहिकाएं",
            "मानव हृदय की संरचना दोहरा परिसंचरण धमनियां शिराएं हीमोग्लोबिन",
            "पादपों में परिवहन जाइलम और फ्लोएम जल और भोजन का संवहन",
            "उत्सर्जन तंत्र मानव वृक्क नेफ्रॉन वृक्काणु मूत्र निर्माण डायलिसिस",
            "नियंत्रण एवं समन्वय तंत्रिका तंत्र न्यूरॉन तंत्रिका कोशिका सिनेप्स प्रतिवर्ती चाप मस्तिष्क मेरुरज्जु",
            "अंतःस्रावी ग्रंथियां हार्मोन पीयूष ग्रंथि थायरॉयड एड्रिनल इंसुलिन अग्न्याशय",
            "जीव जनन कैसे करते हैं अलैंगिक जनन विखंडन मुकुलन पुनरुद्भवन बीजाणु कायिक प्रवर्धन",
            "पुष्पी पौधों में लैंगिक जनन परागण निषेचन अंडाशय बीजांड बीज निर्माण",
            "मानव जनन नर एवं मादा जनन तंत्र मासिक चक्र भ्रूण का विकास",
            "आनुवंशिकता एवं जैव विकास मेंडल के वंशागति के नियम एकसंकर संकरण जीन युग्मविकल्पी",
            "प्रभावी और अप्रभावी लक्षण जीनप्ररूप दृश्यप्ररूप लिंग निर्धारण",
            "डीएनए की संरचना द्विकुंडलिनी मॉडल न्यूक्लियोटाइड प्रतिकृतियन आरएनए",
            "विकास डार्विन प्राकृतिक वरण अनुकूलन समजात अंग जीवाश्म",
            "हमारा पर्यावरण पारितंत्र खाद्य श्रृंखला खाद्य जाल पोषी स्तर जैव आवर्धन ओजोन परत",
            "कोशिका जीवन की इकाई कोशिका सिद्धांत रॉबर्ट हुक श्वान श्लीडेन विरचो",
            "प्रोकैरियोटिक कोशिका और यूकैरियोटिक कोशिका पादप कोशिका जन्तु कोशिका",
            "कोशिकांग केंद्रक अंतःप्रद्रव्यी जालिका गॉल्जी उपकरण लाइसोसोम राइबोसोम",
            "कोशिका विभाजन सूत्री विभाजन और अर्धसूत्री विभाजन", "जैव अणु प्रोटीन न्यूक्लिक अम्ल एंजाइम",
            "पादप जगत और प्राणि जगत कशेरुकी अकशेरुकी", "मानव स्वास्थ्य तथा रोग प्रतिरक्षा टीके प्रतिरक्षी एड्स कैंसर",
            "कोशिका सिद्धांत और इसे किसने प्रतिपादित किया श्वान श्लीडेन",
            "मेंडल के वंशागति के नियम आनुवंशिकता और एकसंकर संकरण"
        ]
    },
    "mathematics": {
        "en": [
            "probability and combinations rolling dice two dice coin tosses",
            "binomial theorem expansion of (a + b)^n formula coefficients",
            "real numbers rational and irrational numbers Euclid division lemma fundamental theorem of arithmetic",
            "polynomials zeros of a polynomial relationship between zeros and coefficients",
            "pair of linear equations in two variables graphical method substitution method elimination method",
            "quadratic equations standard form ax^2+bx+c=0 roots of quadratic equation discriminant b^2-4ac",
            "quadratic formula x=(-b+-sqrt(b^2-4ac))/(2a) nature of roots",
            "arithmetic progressions AP first term common difference nth term an=a+(n-1)d",
            "sum of first n terms of an AP Sn=n/2(2a+(n-1)d) Sn=n/2(a+l)",
            "triangles similar triangles criteria for similarity of triangles AAA SAS SSS",
            "Pythagoras theorem and converse of Pythagoras theorem right-angled triangle hypotenuse",
            "coordinate geometry distance formula sqrt((x2-x1)^2+(y2-y1)^2) section formula midpoint formula",
            "area of a triangle in coordinate geometry collinear points",
            "introduction to trigonometry trigonometric ratios sine cosine tangent cotangent secant cosecant",
            "trigonometric values of specific angles 0 30 45 60 90 degrees",
            "trigonometric identities sin^2+cos^2=1 1+tan^2=sec^2 1+cot^2=cosec^2",
            "some applications of trigonometry heights and distances angle of elevation angle of depression",
            "circles tangent to a circle number of tangents from a point to a circle length of tangents",
            "areas related to circles perimeter and area of circle sector and segment of a circle",
            "surface areas and volumes cube cuboid sphere hemisphere cylinder cone frustum",
            "statistics mean median mode of grouped data empirical relationship between central tendencies",
            "probability theoretical probability P(E)=favorable outcomes/total outcomes sure event impossible event",
            "sets and relations subsets empty set universal set union intersection complement of sets",
            "functions domain range and codomain injective surjective bijective functions",
            "inverse trigonometric functions principal value branch properties of inverse trig functions",
            "matrices types of matrices addition multiplication transpose symmetric and skew-symmetric",
            "determinants properties of determinants minors and cofactors adjoint and inverse of a matrix",
            "continuity and differentiability chain rule derivatives of implicit functions",
            "application of derivatives rate of change increasing decreasing functions tangents normals maxima minima",
            "integrals indefinite integrals integration by substitution integration by parts partial fractions",
            "definite integrals fundamental theorem of calculus properties of definite integrals area under curves",
            "differential equations order and degree general and particular solutions homogeneous differential equations",
            "vector algebra magnitude and direction cosines scalar dot product and vector cross product",
            "three dimensional geometry direction ratios lines and planes in 3D shortest distance between skew lines",
            "linear programming objective function constraints feasible region bounded unbounded optimal solution",
            "probability conditional probability multiplication theorem Bayes' theorem random variable binomial distribution"
        ],
        "te": [
            "వాస్తవ సంఖ్యలు అకరణీయ మరియు కరణీయ సంఖ్యలు యూక్లిడ్ భాగహార న్యాయం అంకగణిత ప్రాథమిక సిద్ధాంతం",
            "బహుపదులు బహుపది శూన్యాలు గుణకాలు మరియు శూన్యాల మధ్య సంబంధం",
            "రెండు చరరాశులలో రేఖీయ సమీకరణాల జత గ్రాఫ్ పద్ధతి ప్రతిక్షేపణ పద్ధతి చరరాశి తొలగింపు పద్ధతి",
            "వర్గ సమీకరణాలు ప్రామాణిక రూపం ax^2+bx+c=0 వర్గ సమీకరణ మూలాలు విచక్షణి b^2-4ac",
            "వర్గ సమీకరణ సూత్రం మూలాల స్వభావం",
            "అంకశ్రేఢి AP మొదటి పదం సామాన్య భేదం nవ పదం సూత్రం an=a+(n-1)d",
            "అంకశ్రేఢిలో మొదటి n పదాల మొత్తం Sn సూత్రం",
            "సరూప త్రిభుజాలు త్రిభుజాల సరూప్యత నియమాలు",
            "పైథాగరస్ సిద్ధాంతం మరియు విపర్యయం లంబకోణ త్రిభుజం కర్ణం",
            "నిరూపక జ్యామితి దూర సూత్రం విభజన సూత్రం మధ్యబిందువు సూత్రం",
            "త్రికోణమితి త్రికోణమితి నిష్పత్తులు సైన్ కొసైన్ టాంజెంట్ కోటాంజెంట్ సీకెంట్ కొసీకెంట్",
            "త్రికోణమితి విలువలు 0 30 45 60 90 డిగ్రీలు",
            "త్రికోణమితి సర్వసమీకరణాలు sin^2+cos^2=1",
            "త్రికోణమితి అనువర్తనాలు ఎత్తులు మరియు దూరాలు ఉన్నతి కోణం నిమ్న కోణం",
            "వృత్తాలు వృత్త స్పర్శరేఖలు స్పర్శరేఖ పొడవు",
            "వృత్త వైశాల్యాలు సెక్టార్ మరియు వృత్త ఖండ వైశాల్యం",
            "ఉపరితల వైశాల్యాలు మరియు ఘనపరిమాణాలు సమఘనం దీర్ఘఘనం స్థూపం శంఖువు గోళం అర్ధగోళం",
            "సాంఖ్యక శాస్త్రం సగటు మధ్యగతం బాహుళకం",
            "సంభావ్యత అనుకూల పర్యవసానాలు మొత్తం పర్యవసానాలు ఖచ్చిత ఘటన అసాధ్య ఘటన",
            "సమితులు మరియు సంబంధాలు ఉపసమితి సమితుల సమ్మేళనం ఛేదనం పూరకం",
            "ప్రమేయాలు ప్రదేశం సహప్రదేశం వ్యాప్తి అన్వేక సంగ్రస్త ద్విగుణ ప్రమేయాలు",
            "విలోమ త్రికోణమితి ప్రమేయాలు ప్రధాన విలువ శాఖ",
            "మాత్రికలు మాత్రిక రకాలు మాత్రిక సంకలనం గుణకారం పరివర్తనం సౌష్టవ అసౌష్టవ మాత్రికలు",
            "నిర్ణాయకాలు ఉపనిర్ణాయకాలు సహగుణకారాలు విలోమ మాత్రిక",
            "అవిచ్ఛిన్నత మరియు అవకలనీయత గొలుసు నియమం అవకలనాలు",
            "అవకలనాల అనువర్తనాలు గరిష్టాలు మరియు కనిష్టాలు రేఖీయ వాలు",
            "సమాకలనం అనిశ్చిత సమాకలనం ప్రతిక్షేపణ పద్ధతి ఖండశః సమాకలనం",
            "ఖచ్చిత సమాకలనాలు వక్రాల కింద వైశాల్యం",
            "అవకలన సమీకరణాలు పరిమాణం మరియు తరగతి",
            "సదిశ బీజగణితం అదిశ బిందు గుణకారం సదిశ గుణకారం డాట్ ప్రొడక్ట్ క్రాస్ ప్రొడక్ట్",
            "త్రిమితీయ జ్యామితి దిక్ కొసైన్లు సరళరేఖలు మరియు తలాలు",
            "రేఖీయ ప్రణాళిక లక్ష్య ప్రమేయం పరిమితులు సాధ్య ప్రాంతం",
            "బేయిస్ సిద్ధాంతం యాదృచ్ఛిక చరరాశి ద్విపద విభాజనం"
        ],
        "hi": [
            "वास्तविक संख्याएं परिमेय और अपरिमेय संख्याएं यूक्लिड विभाजन प्रमेयिका अंकगणित की आधारभूत प्रमेय",
            "बहुपद बहुपद के शून्यक शून्यकों और गुणांकों में संबंध",
            "दो चर वाले रैखिक समीकरण युग्म आलेखीय विधि प्रतिस्थापन विधि विलोपन विधि",
            "द्विघात समीकरण मानक रूप ax^2+bx+c=0 द्विघात समीकरण के मूल विविक्तकर b^2-4ac",
            "द्विघाती सूत्र x=(-b+-sqrt(b^2-4ac))/(2a) मूलों की प्रकृति",
            "समांतर श्रेढ़ियां AP प्रथम पद सार्व अंतर nवां पद an=a+(n-1)d",
            "समांतर श्रेढ़ी के प्रथम n पदों का योगफल Sn सूत्र",
            "त्रिभुज समरूप त्रिभुज त्रिभुजों की समरूपता की कसौटियां",
            "पाइथागोरस प्रमेय और पाइथागोरस प्रमेय का विलोम समकोण त्रिभुज कर्ण",
            "निर्देशांक ज्यामिति दूरी सूत्र विभाजन सूत्र मध्य बिंदु सूत्र",
            "त्रिकोणमिति का परिचय त्रिकोणमितीय अनुपात साइन कोसाइन टैनजेंट कोटैनजेंट सीकेंट कोसीकेंट",
            "विशिष्ट कोणों के त्रिकोणमितीय मान 0 30 45 60 90 अंश",
            "त्रिकोणमितीय सर्वसमिकाएं sin^2+cos^2=1 1+tan^2=sec^2 1+cot^2=cosec^2",
            "त्रिकोणमिति के कुछ अनुप्रयोग ऊंचाइयां और दूरियां उन्नयन कोण अवनमन कोण",
            "वृत्त वृत्त की स्पर्श रेखा स्पर्श रेखा की लंबाई",
            "वृत्तों से संबंधित क्षेत्रफल त्रिज्यखंड और वृत्तखंड का क्षेत्रफल",
            "पृष्ठीय क्षेत्रफल और आयतन घन घनाभ बेलन शंकु गोला अर्धगोला छिन्नक",
            "सांख्यिकी वर्गीकृत आंकड़ों का माध्य माध्यक बहुलक",
            "प्रायिकता सैद्धांतिक प्रायिकता अनुकूल परिणाम कुल परिणाम निश्चित घटना असंभव घटना",
            "समुच्चय और संबंध उपसमुच्चय रिक्त समुच्चय सार्वत्रिक समुच्चय सम्मिलन सर्वनिष्ठ पूरक",
            "फलन प्रांत सहप्रांत परिसर एकैकी आच्छादक फलन",
            "प्रतिलोम त्रिकोणमितीय फलन मुख्य मान शाखा",
            "आव्यूह आव्यूह के प्रकार आव्यूह का योग गुणन परिवर्त सममित विषम सममित आव्यूह",
            "सारणिक सारणिक के गुणधर्म उपसारणिक सहखंड व्युत्क्रम आव्यूह",
            "सांतत्य तथा अवकलनीयता शृंखला नियम अस्पष्ट फलनों के अवकलज",
            "अवकलज के अनुप्रयोग परिवर्तन की दर वर्धमान ह्रासमान फलन स्पर्श रेखाएं अभिलंब उच्चिष्ठ निम्निष्ठ",
            "समाकलन अनिश्चित समाकलन प्रतिस्थापन द्वारा समाकलन खंडशः समाकलन आंशिक भिन्न",
            "निश्चित समाकलन समाकलन की आधारभूत प्रमेय वक्रों के अंतर्गत क्षेत्रफल",
            "अवकल समीकरण कोटि और घात समघातीय अवकल समीकरण",
            "सदिश बीजगणित परिमाण और दिशा कोसाइन अदिश गुणनफल सदिश गुणनफल डॉट क्रॉस",
            "त्रिविमीय ज्यामिति दिक-अनुपात रेखाएं और समतल",
            "रैखिक प्रोग्रामन उद्देश्य फलन व्यवरोध सुसंगत क्षेत्र इष्टतम हल",
            "बेज प्रमेय यादृच्छिक चर द्विपद बंटन प्रायिकता बंटन"
        ]
    }
}

def build_training_set():
    meta_path = api_dir / "faiss_index_v2" / "metadata.json"
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    texts = []
    labels = []

    # Map for FAISS metadata chunks
    subj_map = {
        "physics": "physics",
        "chemistry": "chemistry",
        "biology": "biology",
        "maths": "mathematics",
        "mathematics": "mathematics",
    }

    # 1. FAISS chunks (balanced limit 1000 per class)
    counts = Counter()
    for item in metadata:
        s = subj_map.get(item.get("subject", "").lower())
        if not s or counts[s] >= 1000:
            continue
        txt = item.get("text", "").strip()
        if len(txt) > 40:
            texts.append(txt[:400])
            labels.append(s)
            counts[s] += 1
            ch = item.get("chapter", "").strip()
            if ch and len(ch) > 4:
                texts.append(ch)
                labels.append(s)

    print("From FAISS metadata:", counts)

    # 2. Rich Multilingual Curriculum entries (repeated for balance weight)
    for subj, lang_dict in CURRICULUM_DATA.items():
        for lang, entries in lang_dict.items():
            for entry in entries:
                # Add bare entry
                texts.append(entry)
                labels.append(subj)
                # Add natural query template variations
                if lang == "en":
                    texts.append(f"What is {entry} and explain its formula?")
                    labels.append(subj)
                    texts.append(f"Explain {entry} with examples.")
                    labels.append(subj)
                elif lang == "te":
                    texts.append(f"{entry} అంటే ఏమిటి మరియు వివరించండి.")
                    labels.append(subj)
                    texts.append(f"{entry} సూత్రం మరియు ప్రాముఖ్యత ఏమిటి?")
                    labels.append(subj)
                elif lang == "hi":
                    texts.append(f"{entry} क्या है और इसका सूत्र समझाइए।")
                    labels.append(subj)
                    texts.append(f"{entry} की परिभाषा और उदाहरण दीजिए।")
                    labels.append(subj)

    print("Total training texts:", len(texts))
    print("Class distribution:", Counter(labels))
    return texts, labels

def train():
    texts, labels = build_training_set()

    print("\nTraining FeatureUnion Pipeline...")
    pipeline = Pipeline([
        ("features", FeatureUnion([
            ("word_tfidf", TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                max_features=40000,
                token_pattern=r"(?u)\b\w+\b"
            )),
            ("char_tfidf", TfidfVectorizer(
                ngram_range=(3, 5),
                analyzer="char_wb",
                sublinear_tf=True,
                max_features=60000
            ))
        ])),
        ("clf", LogisticRegression(
            C=3.0,
            max_iter=600,
            solver="lbfgs",
            class_weight="balanced",
            random_state=42
        ))
    ])

    pipeline.fit(texts, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved successfully to {MODEL_PATH} ({MODEL_PATH.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    train()
