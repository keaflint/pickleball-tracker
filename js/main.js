// Smooth scrolling for navigation links
document.querySelectorAll('nav a').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const section = document.querySelector(this.getAttribute('href'));
        section.scrollIntoView({ behavior: 'smooth' });
    });
});

// Add click handler for CTA button
document.querySelector('.cta-button').addEventListener('click', () => {
    // This will be updated when we add the game tracking functionality
    alert('Game tracking feature coming soon!');
}); 