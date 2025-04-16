TEXT_INFO_EXTRACTION_PROMPT = (
    "You will receive a text. Your task is to extract structured information from it"
    "for use by another language model. First, extract the title and author if "
    "identifiable; otherwise, return them as false. Then, generate a detailed "
    "and information-rich summary specifically for LLM processing. This summary "
    "must be comprehensive enough to allow another LLM to understand the"
    " original document's purpose and content without having direct access to it."
    "\n\nInclude the following in the summary:"
    "\n1) The main topic or theme."
    "\n2) A full content overview, summarizing all key arguments, events, or ideas."
    "\n3) The document’s genre (e.g., fiction, scientific paper, opinion piece, legal contract)."
    "\n4) All explicitly and implicitly mentioned entities (people, organizations, places, concepts)."
    "\n5) The tone, intent, and style of the writing (e.g., persuasive, descriptive, formal)."
    "\n6) Any domain-specific context or knowledge assumed by the text."
    "\n7) Any relevant structure or formatting patterns (e.g., chapters, dialogue, citations)."
    "\n\nBe as specific and complete as possible in the summary, even if the original text is long."
)

WORD_EXTRACTION_PROMPT = (
    "You will receive two inputs:"
    "\n1. A context summary describing the content, topic, genre, entities, tone, and structure of a document."
    "\n2. A list of words extracted from the document, each with its frequency of occurrence."
    "\n\nYour task is to identify and return only the words that are contextually relevant to the document, "
    "based on the information provided in the summary."
    "\n\nContextually relevant words are those that:"
    "\n1) Relate directly to the main topic, subject matter, or themes."
    "\n2) Represent key entities, concepts, or domain-specific terminology."
    "\n3) Are important for understanding the content, structure, or intent of the document."
    "\n4) May include uncommon or high-signal terms, even if they are low in frequency."
    "\nDo not return general-purpose or filler words (e.g., 'the', 'also', 'very') unless they carry domain-specific importance."
    "\nDo not rely solely on frequency — use the summary to infer what matters."
)

