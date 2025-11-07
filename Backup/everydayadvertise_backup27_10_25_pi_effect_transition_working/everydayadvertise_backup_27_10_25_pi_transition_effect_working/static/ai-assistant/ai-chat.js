// AI Assistant Chat System
class AIAssistant {
  constructor() {
    this.isOpen = false;
    this.messages = [];
    this.initializeKnowledgeBase();
    this.init();
  }

  initializeKnowledgeBase() {
    // Knowledge base for the AI assistant
    this.knowledgeBase = {
      'how to use': {
        keywords: ['how', 'use', 'start', 'begin', 'setup', 'work'],
        response: `Getting started with EverydayAdvertise is super easy! 🚀

1. **Sign Up**: Click "Get Started Free" - no credit card required
2. **Upload Content**: Add your menu items, images, and videos
3. **Connect Screens**: Download our app on your TV or Pi device
4. **Go Live**: Your digital menu is ready!

Setup takes just 5 minutes. Need help? Our support team is available 24/7!`
      },
      'pricing': {
        keywords: ['price', 'cost', 'fee', 'payment', 'plan', 'subscription'],
        response: `Our pricing is transparent and flexible! 💰

✨ **Free Trial**: 14 days, all features included
📱 **Starter Plan**: $29/month - Up to 3 screens
🚀 **Professional**: $79/month - Up to 10 screens
🏢 **Enterprise**: Custom pricing - Unlimited screens

All plans include:
- Unlimited content updates
- Cloud sync across all screens
- 24/7 support
- No setup fees

Want to discuss custom pricing? Contact our sales team!`
      },
      'features': {
        keywords: ['feature', 'what can', 'capability', 'function', 'do'],
        response: `EverydayAdvertise is packed with amazing features! ✨

🎯 **Key Features**:
- **Real-time Sync**: All screens update instantly
- **Video Walls**: Create stunning multi-screen displays
- **Smart Scheduling**: Auto-update menus by time of day
- **Cloud Storage**: Access from anywhere
- **Template Library**: Pre-designed menu templates
- **Analytics**: Track what customers view most
- **Multi-location**: Manage all restaurants from one dashboard
- **Easy Updates**: Change menus in seconds

Everything updates in real-time across all your screens!`
      },
      'sync': {
        keywords: ['sync', 'synchronize', 'together', 'multiple screens', 'video wall'],
        response: `Our sync technology is world-class! 🌍

**How it works**:
- All screens connect to our cloud platform
- Changes sync in under 2 seconds
- Perfect frame-by-frame synchronization
- Create video walls with multiple TVs
- Works on any device (TV, tablet, Pi)

We're the **World's First Sync Digital Menu on TV** - our technology ensures your content plays perfectly across unlimited screens simultaneously!`
      },
      'devices': {
        keywords: ['device', 'tv', 'tablet', 'raspberry pi', 'android', 'fire tv', 'compatible'],
        response: `We support all major platforms! 📱

✅ **Compatible Devices**:
- 🖥️ Smart TVs (Android TV, LG webOS, Samsung Tizen)
- 🔥 Amazon Fire TV Stick
- 📱 Android Tablets
- 🍓 Raspberry Pi (optimized app)
- 💻 Any device with a web browser

**Installation**: Simple app download or web player
**Network**: Works on WiFi or ethernet
**Resolution**: Up to 4K supported

Just need internet connection - that's it!`
      },
      'support': {
        keywords: ['support', 'help', 'problem', 'issue', 'contact', 'assistance'],
        response: `We're here to help 24/7! 🛟

**Get Support**:
- 💬 Live Chat: Available right now
- 📧 Email: service@everydayadvertise.com
- 📞 Phone: Available 24/7
- 📚 Help Center: Detailed guides & videos

**Response Times**:
- Live Chat: Instant
- Email: Within 2 hours
- Phone: Available 24/7

We also offer free onboarding training for new customers!`
      },
      'update': {
        keywords: ['update', 'change', 'edit', 'modify', 'content'],
        response: `Updating your menus is super fast! ⚡

**How to Update**:
1. Log into your dashboard
2. Click "Edit Menu" or "Add Content"
3. Upload images/videos or edit prices
4. Hit "Publish"
5. Changes sync to all screens in 2 seconds!

**What you can update**:
- Menu items & prices
- Images & videos
- Promotions & specials
- Layouts & templates
- Schedules & playlists

No technical skills required - it's as easy as posting on social media!`
      },
      'demo': {
        keywords: ['demo', 'trial', 'test', 'try', 'preview', 'example'],
        response: `Want to see it in action? 🎬

**Try EverydayAdvertise**:
- 📺 Watch live demos on this page
- 🆓 Start 14-day free trial (no credit card)
- 📞 Schedule a personalized demo
- 🎥 View our video tutorials

**What you'll see**:
- Real-time sync across screens
- Easy content management
- Video wall capabilities
- Mobile dashboard

Click "Watch Demo" button or "Get Started Free" to begin!`
      },
      'greeting': {
        keywords: ['hello', 'hi', 'hey', 'greetings'],
        response: `Hello! 👋 I'm your AI assistant for EverydayAdvertise!

I can help you with:
- 🚀 How to get started
- 💰 Pricing information
- ✨ Features & capabilities
- 🔧 Technical support
- 📱 Device compatibility

What would you like to know?`
      }
    };

    // Quick questions for easy access
    this.quickQuestions = [
      'How do I get started?',
      'What are the pricing plans?',
      'What devices are supported?',
      'How does sync work?',
      'Can I try it for free?'
    ];
  }

  init() {
    this.createChatWidget();
    this.attachEventListeners();
    this.showWelcomeMessage();
  }

  createChatWidget() {
    const chatHTML = `
      <!-- AI Chat Button -->
      <button class="ai-chat-button" id="aiChatButton">
        <span class="ai-robot-icon">🤖</span>
      </button>

      <!-- AI Chat Window -->
      <div class="ai-chat-window" id="aiChatWindow">
        <!-- Header -->
        <div class="ai-chat-header">
          <div class="ai-header-content">
            <div class="ai-avatar">🤖</div>
            <div class="ai-info">
              <h3>AI Assistant</h3>
              <div class="ai-status">
                <span class="status-dot"></span>
                <span>Online</span>
              </div>
            </div>
          </div>
          <button class="ai-close-btn" id="aiCloseBtn">✕</button>
        </div>

        <!-- Messages Area -->
        <div class="ai-chat-messages" id="aiChatMessages">
          <!-- Messages will be inserted here -->
        </div>

        <!-- Input Area -->
        <div class="ai-chat-input-area">
          <input 
            type="text" 
            class="ai-chat-input" 
            id="aiChatInput" 
            placeholder="Ask me anything..."
            autocomplete="off"
          />
          <button class="ai-send-btn" id="aiSendBtn">
            <span>➤</span>
          </button>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', chatHTML);
  }

  attachEventListeners() {
    const chatButton = document.getElementById('aiChatButton');
    const chatWindow = document.getElementById('aiChatWindow');
    const closeBtn = document.getElementById('aiCloseBtn');
    const sendBtn = document.getElementById('aiSendBtn');
    const input = document.getElementById('aiChatInput');

    chatButton.addEventListener('click', () => this.toggleChat());
    closeBtn.addEventListener('click', () => this.toggleChat());
    sendBtn.addEventListener('click', () => this.sendMessage());
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') this.sendMessage();
    });
  }

  toggleChat() {
    this.isOpen = !this.isOpen;
    const chatWindow = document.getElementById('aiChatWindow');
    const chatButton = document.getElementById('aiChatButton');
    
    chatWindow.classList.toggle('active');
    chatButton.classList.toggle('active');

    if (this.isOpen) {
      document.getElementById('aiChatInput').focus();
      this.scrollToBottom();
    }
  }

  showWelcomeMessage() {
    setTimeout(() => {
      this.addMessage('bot', this.knowledgeBase.greeting.response);
      this.showQuickQuestions();
    }, 500);
  }

  addMessage(type, text) {
    const messagesContainer = document.getElementById('aiChatMessages');
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const messageHTML = `
      <div class="ai-message ${type}">
        <div class="message-avatar">${type === 'bot' ? '🤖' : '👤'}</div>
        <div class="message-content">
          <div class="message-bubble">${text.replace(/\n/g, '<br>')}</div>
          <div class="message-time">${time}</div>
        </div>
      </div>
    `;

    messagesContainer.insertAdjacentHTML('beforeend', messageHTML);
    this.scrollToBottom();
  }

  showQuickQuestions() {
    const messagesContainer = document.getElementById('aiChatMessages');
    const questionsHTML = `
      <div class="quick-questions">
        ${this.quickQuestions.map(q => 
          `<button class="quick-question-btn" onclick="aiAssistant.handleQuickQuestion('${q}')">${q}</button>`
        ).join('')}
      </div>
    `;
    messagesContainer.insertAdjacentHTML('beforeend', questionsHTML);
    this.scrollToBottom();
  }

  handleQuickQuestion(question) {
    // Remove quick questions after selection
    const quickQuestions = document.querySelector('.quick-questions');
    if (quickQuestions) quickQuestions.remove();
    
    // Send the question
    this.addMessage('user', question);
    this.processMessage(question);
  }

  sendMessage() {
    const input = document.getElementById('aiChatInput');
    const message = input.value.trim();

    if (!message) return;

    this.addMessage('user', message);
    input.value = '';

    this.showTypingIndicator();
    
    setTimeout(() => {
      this.hideTypingIndicator();
      this.processMessage(message);
    }, 1000 + Math.random() * 1000);
  }

  processMessage(message) {
    const lowerMessage = message.toLowerCase();
    let response = null;

    // Find matching knowledge base entry
    for (const [key, data] of Object.entries(this.knowledgeBase)) {
      if (data.keywords.some(keyword => lowerMessage.includes(keyword))) {
        response = data.response;
        break;
      }
    }

    // Default response if no match found
    if (!response) {
      response = `I'd be happy to help! 😊

I can answer questions about:
- 🚀 Getting started & setup
- 💰 Pricing & plans
- ✨ Features & capabilities
- 📱 Device compatibility
- 🔧 Technical support
- 📺 How sync works

You can also:
- Click "Get Started Free" for a 14-day trial
- Schedule a demo call
- Chat with our support team

What would you like to know more about?`;
    }

    this.addMessage('bot', response);
  }

  showTypingIndicator() {
    const messagesContainer = document.getElementById('aiChatMessages');
    const typingHTML = `
      <div class="ai-message bot typing-message">
        <div class="message-avatar">🤖</div>
        <div class="typing-indicator active">
          <div class="typing-dots">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>
    `;
    messagesContainer.insertAdjacentHTML('beforeend', typingHTML);
    this.scrollToBottom();
  }

  hideTypingIndicator() {
    const typingMessage = document.querySelector('.typing-message');
    if (typingMessage) typingMessage.remove();
  }

  scrollToBottom() {
    const messagesContainer = document.getElementById('aiChatMessages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

// Initialize AI Assistant when page loads
let aiAssistant;
document.addEventListener('DOMContentLoaded', () => {
  aiAssistant = new AIAssistant();
});
