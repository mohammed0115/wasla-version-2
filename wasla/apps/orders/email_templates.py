"""Order confirmation email templates."""


def render_order_confirmation_email(order):
    """
    Render order confirmation email in HTML format.

    Args:
        order: Order instance

    Returns:
        str: HTML email body
    """
    # Calculate VAT and totals
    vat_amount = order.total_amount - order.subtotal if hasattr(order, 'subtotal') else order.total_amount * 0.15
    
    # Format items
    items_html = ""
    for item in order.items.all():
        items_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 12px; text-align: left;">{item.product.name}</td>
            <td style="padding: 12px; text-align: center;">{item.quantity}</td>
            <td style="padding: 12px; text-align: right;">{item.unit_price} SAR</td>
            <td style="padding: 12px; text-align: right;">{item.total_price} SAR</td>
        </tr>
        """

    # Calculate subtotal (before VAT)
    subtotal = sum(item.total_price for item in order.items.all())
    
    # Get store info
    store = order.store if hasattr(order, 'store') else None
    store_name = store.name if store else "Wasla Store"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 600;
            }}
            .content {{
                padding: 30px;
            }}
            .order-number {{
                font-size: 14px;
                color: #666;
                margin-top: 10px;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section-title {{
                font-size: 14px;
                font-weight: 600;
                color: #333;
                text-transform: uppercase;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
                margin-bottom: 15px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th {{
                text-align: left;
                padding: 12px;
                background-color: #f5f5f5;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                color: #666;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .totals {{
                border-top: 2px solid #667eea;
                padding-top: 20px;
            }}
            .total-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                font-size: 14px;
            }}
            .total-row.final {{
                font-size: 18px;
                font-weight: 600;
                color: #667eea;
                border-top: 1px solid #e0e0e0;
                padding-top: 15px;
                margin-top: 10px;
            }}
            .vat-breakdown {{
                background-color: #f9f9f9;
                padding: 15px;
                border-radius: 4px;
                margin: 15px 0;
            }}
            .vat-item {{
                display: flex;
                justify-content: space-between;
                font-size: 13px;
                padding: 5px 0;
            }}
            .address-block {{
                background-color: #f9f9f9;
                padding: 15px;
                border-radius: 4px;
                font-size: 13px;
                line-height: 1.6;
            }}
            .footer {{
                background-color: #f5f5f5;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
                border-top: 1px solid #e0e0e0;
            }}
            .cta-button {{
                display: inline-block;
                background-color: #667eea;
                color: white;
                padding: 12px 30px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: 600;
                margin: 20px 0;
            }}
            .cta-button:hover {{
                background-color: #5568d3;
            }}
            .status {{
                background-color: #e8f5e9;
                border-left: 4px solid #4caf50;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✓ Order Confirmed</h1>
                <div class="order-number">Order #<strong>{order.id}</strong></div>
            </div>

            <div class="content">
                <p>Thank you for your order! We've received it and are preparing it for shipment.</p>

                <div class="status">
                    <strong>Order Status:</strong> {order.get_status_display() if hasattr(order, 'get_status_display') else 'Pending'}
                </div>

                <!-- Order Items -->
                <div class="section">
                    <div class="section-title">Order Items</div>
                    <table>
                        <thead>
                            <tr>
                                <th>Product</th>
                                <th>Qty</th>
                                <th>Unit Price</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>

                    <div class="totals">
                        <div class="total-row">
                            <span>Subtotal:</span>
                            <span>{subtotal} SAR</span>
                        </div>
                        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 4px; margin: 15px 0;">
                            <div class="vat-item">
                                <span>VAT (15%):</span>
                                <span>+{vat_amount:.2f} SAR</span>
                            </div>
                        </div>
                        <div class="total-row final">
                            <span>Order Total:</span>
                            <span>{order.total_amount} SAR</span>
                        </div>
                    </div>
                </div>

                <!-- Shipping Address -->
                {f'''
                <div class="section">
                    <div class="section-title">Shipping Address</div>
                    <div class="address-block">
                        <strong>{order.shipping_address.full_name if hasattr(order, 'shipping_address') else 'N/A'}</strong><br>
                        {order.shipping_address.line1 if hasattr(order, 'shipping_address') else ''}<br>
                        {order.shipping_address.line2 if hasattr(order, 'shipping_address') else ''}<br>
                        {order.shipping_address.city if hasattr(order, 'shipping_address') else ''}, {order.shipping_address.country if hasattr(order, 'shipping_address') else ''} {order.shipping_address.zip_code if hasattr(order, 'shipping_address') else ''}
                    </div>
                </div>
                ''' if hasattr(order, 'shipping_address') else ''}

                <!-- Next Steps -->
                <div class="section">
                    <div class="section-title">What's Next?</div>
                    <p>Your order is being prepared for shipment. You'll receive a tracking number via email as soon as it ships.</p>
                    <a href="#" class="cta-button">Track Your Order</a>
                </div>

                <!-- Contact -->
                <div class="section">
                    <div class="section-title">Questions?</div>
                    <p>If you have any questions about your order, please don't hesitate to contact us. We're here to help!</p>
                    <p>
                        <strong>{store_name}</strong><br>
                        {f'Email: {store.email}' if store and hasattr(store, 'email') else 'support@wasla.sa'}<br>
                        {f'Phone: {store.phone}' if store and hasattr(store, 'phone') else 'N/A'}
                    </p>
                </div>
            </div>

            <div class="footer">
                <p>&copy; 2026 {store_name}. All rights reserved.</p>
                <p style="margin: 5px 0; font-size: 11px;">
                    This is an automated message, please do not reply to this email.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return html_content


def render_order_shipped_email(order, shipment):
    """Render order shipped notification email."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .tracking-box {{ background-color: #f0f7ff; border-left: 4px solid #667eea; padding: 15px; margin: 20px 0; }}
            .tracking-code {{ font-size: 18px; font-weight: 600; color: #667eea; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📦 Your Order Has Shipped!</h1>
            </div>
            <div class="content">
                <p>Great news! Your order #<strong>{order.id}</strong> has been shipped.</p>

                <div class="tracking-box">
                    <p><strong>Tracking Number:</strong></p>
                    <div class="tracking-code">{shipment.tracking_number}</div>
                    <p style="margin-top: 10px; color: #666; font-size: 12px;">
                        Carrier: <strong>{shipment.carrier}</strong>
                    </p>
                </div>

                <p>You can track your shipment using the tracking number above. It will be updated as your package moves through our system.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content
