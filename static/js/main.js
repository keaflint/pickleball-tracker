function initializePlayerInputs() {
    const playerInputs = document.querySelectorAll('.player-input');
    
    playerInputs.forEach(input => {
        const wrapper = document.createElement('div');
        wrapper.className = 'player-input-wrapper';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        
        const suggestionsList = document.createElement('ul');
        suggestionsList.className = 'player-suggestions';
        wrapper.appendChild(suggestionsList);
        
        let currentFocus = -1;
        
        input.addEventListener('input', debounce(async function(e) {
            const query = this.value.trim();
            suggestionsList.innerHTML = '';
            currentFocus = -1;
            
            if (query.length < 2) return;
            
            try {
                const response = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
                const users = await response.json();
                
                users.forEach(user => {
                    const li = document.createElement('li');
                    li.textContent = user.username;
                    li.addEventListener('click', () => {
                        input.value = user.username;
                        suggestionsList.innerHTML = '';
                    });
                    suggestionsList.appendChild(li);
                });
            } catch (error) {
                console.error('Error fetching users:', error);
            }
        }, 300));
        
        // Handle keyboard navigation
        input.addEventListener('keydown', function(e) {
            const items = suggestionsList.getElementsByTagName('li');
            
            if (e.key === 'ArrowDown') {
                currentFocus++;
                addActive(items);
                e.preventDefault();
            } else if (e.key === 'ArrowUp') {
                currentFocus--;
                addActive(items);
                e.preventDefault();
            } else if (e.key === 'Enter' && currentFocus > -1) {
                if (items[currentFocus]) {
                    items[currentFocus].click();
                    e.preventDefault();
                }
            }
        });
        
        // Close suggestions on click outside
        document.addEventListener('click', function(e) {
            if (!wrapper.contains(e.target)) {
                suggestionsList.innerHTML = '';
            }
        });
    });
}

function addActive(items) {
    if (!items) return;
    
    removeActive(items);
    
    if (currentFocus >= items.length) currentFocus = 0;
    if (currentFocus < 0) currentFocus = items.length - 1;
    
    items[currentFocus].classList.add('active');
}

function removeActive(items) {
    for (let i = 0; i < items.length; i++) {
        items[i].classList.remove('active');
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function initializeDatePicker() {
    const dateInput = document.getElementById('date');
    if (dateInput) {
        // Set max date to today
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        dateInput.max = formattedDate;
        
        // Set default value to today
        dateInput.value = formattedDate;
        
        // Add change listener to validate date
        dateInput.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            if (selectedDate > today) {
                alert('Cannot select future dates');
                this.value = formattedDate;
            }
        });
    }
}

function initializeTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return; // Guard clause in case button doesn't exist
    
    // Check for saved theme preference or use system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const preferredTheme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
    
    // Set initial theme
    document.documentElement.setAttribute('data-theme', preferredTheme);
    
    // Add click event listener
    themeToggle.addEventListener('click', function() {
        // Toggle theme
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        // Update theme
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });
}

function togglePlayers() {
    const gameType = document.getElementById('game_type').value;
    const doublesFields = document.querySelectorAll('.doubles-only');
    
    doublesFields.forEach(field => {
        if (gameType === 'doubles') {
            field.style.display = 'block';
            field.querySelector('input').required = true;
        } else {
            field.style.display = 'none';
            field.querySelector('input').required = false;
        }
    });
}

// AI Chat for Game Entry
const aiChatButton = document.getElementById('aiChatButton');
const aiChatModal = document.getElementById('aiChatModal');
const aiChatInput = document.getElementById('aiChatInput');
const aiChatSubmit = document.getElementById('aiChatSubmit');
const aiChatMessages = document.getElementById('aiChatMessages');

if (aiChatButton) {
    aiChatButton.addEventListener('click', () => {
        aiChatModal.style.display = 'block';
    });

    aiChatSubmit.addEventListener('click', async () => {
        const message = aiChatInput.value.trim();
        if (!message) return;

        // Add user message to chat
        appendMessage('user', message);
        aiChatInput.value = '';

        try {
            const response = await fetch('/api/chat/game_entry', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            const data = await response.json();
            
            // Add AI response to chat
            appendMessage('ai', data.response);

            // If game data was extracted, populate the form
            if (data.game_data) {
                populateGameForm(data.game_data);
                aiChatModal.style.display = 'none';
            }
        } catch (error) {
            console.error('Error in AI chat:', error);
            appendMessage('system', 'Sorry, there was an error processing your request.');
        }
    });
}

function appendMessage(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}-message`;
    messageDiv.textContent = content;
    aiChatMessages.appendChild(messageDiv);
    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
}

function populateGameForm(gameData) {
    // Set game type
    const gameTypeSelect = document.getElementById('gameType');
    if (gameTypeSelect) {
        gameTypeSelect.value = gameData.game_type;
        gameTypeSelect.dispatchEvent(new Event('change'));
    }

    // Set date
    const dateInput = document.getElementById('gameDate');
    if (dateInput && gameData.date) {
        dateInput.value = gameData.date;
    }

    // Set scores
    const team1Score = document.querySelector('input[name="team1_score"]');
    const team2Score = document.querySelector('input[name="team2_score"]');
    if (team1Score && team2Score) {
        team1Score.value = gameData.team1_score;
        team2Score.value = gameData.team2_score;
    }

    // Set other fields if they exist
    const fields = ['location', 'duration', 'tournament', 'surface', 'skill', 'weather'];
    fields.forEach(field => {
        const input = document.getElementById(field);
        if (input && gameData[field]) {
            input.value = gameData[field];
        }
    });

    // Set players (after the player fields are created by the game type change event)
    setTimeout(() => {
        const playerSelects = document.querySelectorAll('.player-select');
        if (gameData.players && playerSelects) {
            gameData.players.forEach((playerId, index) => {
                if (playerSelects[index]) {
                    playerSelects[index].value = playerId;
                }
            });
        }
    }, 100);
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', function() {
    initializePlayerInputs();
    togglePlayers();
    initializeDatePicker();
    initializeTheme();
    
    // Set max date for date input
    const dateInput = document.getElementById('gameDate');
    if (dateInput) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        const formattedDate = `${yyyy}-${mm}-${dd}`;
        
        dateInput.max = formattedDate;
        
        // If no date is set, set it to today
        if (!dateInput.value) {
            dateInput.value = formattedDate;
        }
        
        // Prevent future dates from being entered manually
        dateInput.addEventListener('input', function() {
            const selectedDate = new Date(this.value);
            if (selectedDate > today) {
                this.value = formattedDate;
            }
        });
    }
});

// Also run immediately to prevent flash of wrong theme
initializeTheme();