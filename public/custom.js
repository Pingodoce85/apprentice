setTimeout(function() {
    if (!document.getElementById('fieldbook-title')) {
        var title = document.createElement('div');
        title.id = 'fieldbook-title';
        title.innerHTML = '<h1 style="text-align:center;font-size:5rem;font-weight:700;color:white;margin:0;padding:0;letter-spacing:-2px;">Fieldbook</h1><p style="text-align:center;color:#888;font-size:1rem;margin-top:0.5rem;">Your personal AI-powered mechanical contracting assistant.</p>';
        title.style.cssText = 'position:fixed;top:35%;left:50%;transform:translate(-50%,-50%);z-index:10;width:100%;pointer-events:none;';
        document.body.appendChild(title);
    }

    if (!document.getElementById('fieldbook-brand')) {
        var brand = document.createElement('div');
        brand.id = 'fieldbook-brand';
        brand.innerText = 'Fieldbook';
        brand.style.cssText = 'position:fixed;top:50px;left:16px;font-size:2.2rem;font-weight:700;letter-spacing:-1px;z-index:9999;color:white;display:none;cursor:pointer;';
        if (document.documentElement.classList.contains('light')) brand.style.color = 'black';
        document.body.appendChild(brand);
    }

    if (!document.getElementById('composer-style')) {
        var style = document.createElement('style');
        style.id = 'composer-style';
        style.innerHTML = '#message-composer { position:fixed !important; bottom:auto !important; top:52% !important; left:50% !important; transform:translateX(-50%) !important; width:600px !important; max-width:72% !important; }';
        document.head.appendChild(style);
    }

    document.addEventListener('click', function(e) {
        if (e.target.id === 'fieldbook-brand') {
            if (confirm('Are you sure you want to start a new session? All current conversations will be lost.')) window.location.reload();
        }
    });

    function enterConversationMode() {
        var title = document.getElementById('fieldbook-title');
        if (title) title.style.display = 'none';
        var brand = document.getElementById('fieldbook-brand');
        if (brand) brand.style.display = 'block';
        var style = document.getElementById('composer-style');
        if (style) style.remove();
    }

    document.addEventListener('click', function(e) {
        var btn = e.target.closest('button');
        if (btn && btn.closest('#message-composer')) enterConversationMode();
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) enterConversationMode();
    });
}, 500);

// Hide avatar circles on load
document.querySelectorAll('span.relative.flex.h-8.w-8, span.relative.flex.shrink-0').forEach(function(el) { el.style.display = 'none'; });
